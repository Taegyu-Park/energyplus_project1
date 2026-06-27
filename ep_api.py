import sys
import math

# 1. EnergyPlus 설치 경로 설정 (본인 버전에 맞게 수정)
# 이 경로 안에 pyenergyplus 폴더가 있어야 합니다.
sys.path.insert(0, 'C:/EnergyPlusV23-1-0') 
from pyenergyplus.api import EnergyPlusAPI

# 2. 실시간 개입을 위한 콜백(Callback) 함수 정의
def python_callback_function(state_argument):
    """
    EnergyPlus가 매 타임스텝 연산을 시작하기 직전에 
    이 함수 안으로 자동으로 들어옵니다. (엔진은 일시정지 상태)
    """
    # 최초 실행 시(Warm-up 단계 등) 변수가 아직 준비 안 되었으면 통과
    if api.exchange.api_data_fully_initialized(state_argument) is False:
        return

    # --- (1) EnergyPlus로부터 현재 태양 위치 가져오기 ---
    # Sun Azimuth(방위각), Sun Altitude(고도각) 변수 핸들 가져오기
    sun_azimuth_handle = api.exchange.get_variable_handle(state_argument, "Site Sun Azimuth Angle", "Environment")
    sun_altitude_handle = api.exchange.get_variable_handle(state_argument, "Site Sun Altitude Angle", "Environment")
    
    sun_az_value = api.exchange.get_variable_value(state_argument, sun_azimuth_handle)
    sun_alt_value = api.exchange.get_variable_value(state_argument, sun_altitude_handle)

    # --- (2) 파이썬 내부에서 가변 PV 각도 및 실제 일사량 계산 ---
    # 예시: 태양 고도(sun_alt_value)에 따라 PV 패널이 가변 추적(Tracking)한다고 가정
    # 여기에 질문자님이 라이노에서 쓰시던 가변 각도 계산 수식을 넣으시면 됩니다.
    # 최종적으로 "변형된 각도일 때 패널이 받는 일사량(W/m²)"을 계산합니다.
    calculated_solar_radiation = 500.0 + (sun_alt_value * 5.5)  # 임의의 수식 예시

    # --- (3) EnergyPlus 엔진의 메모리에 계산된 일사량 강제 주입 (Actuator) ---
    # 주입할 대상(Actuator)의 핸들을 가져옵니다.
    # 규칙: (오브젝트 타입, 컴포넌트 타입, 고유 이름)
    shading_actuator_handle = api.exchange.get_actuator_handle(
        state_argument, 
        "Weather Data", 
        "Plane In Plane Sky Diffuse Solar Radiation Profile", # 혹은 Direct Solar
        "PV_Panel_Surface" # IDF에 적어둔 Surface 이름
    )
    
    # 메모리 값 덮어쓰기!
    api.exchange.set_actuator_value(state_argument, shading_actuator_handle, calculated_solar_radiation)

    # --- (4) EnergyPlus가 계산한 PV 발전량 실시간 탈취 (Variable) ---
    pv_power_handle = api.exchange.get_variable_handle(
        state_argument, 
        "Generator Produced DC Electricity Rate", 
        "Photovoltaic_Generator_Name"
    )
    current_pv_power = api.exchange.get_variable_value(state_argument, pv_power_handle)
    
    # 결과를 파이썬 리스트에 저장하거나 출력 가능
    # print(f"현재 태양고도: {sun_alt_value:.2f}, 주입일사량: {calculated_solar_radiation:.2f}, 발전량: {current_pv_power:.2f}W")


# 3. 메인 가동 스크립트
if __name__ == "__main__":
    # API 인스턴스 및 상태(State) 생성
    api = EnergyPlusAPI()
    state = api.state_manager.new_state()

    # ⭐ 핵심: EnergyPlus 엔진에 파이썬 콜백 함수 등록
    # "매 타임스텝 환경 계산 단계 시작 직전(BeginTimestepBeforePredictor)"에 위 함수를 실행하라는 뜻
    api.runtime.callback_begin_system_timestep_before_predictor(state, python_callback_function)

    # EnergyPlus 실행 명령 인자 설정
    arguments = [
        "-d", "C:/EP_Output",  # 시뮬레이션 결과 파일들이 저장될 경로
        "-w", "C:/EnergyPlusV23-1-0/WeatherData/Seoul_Korea.epw",  # 기상파일 경로
        "C:/EP_Input/Base_Model.idf"  # 고정 PV가 들어있는 IDF 파일 경로
    ]

    print("🚀 EnergyPlus 엔진 가동 (파이썬 실시간 제어 모드)")
    # 엔진 구동 (이 함수가 실행되면 1년 치 연산이 끝날 때까지 프로세스가 켜진 채로 유지됨)
    api.runtime.run_energyplus(state, arguments)
    print("🏁 시뮬레이션 완료!")