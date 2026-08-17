param()

$basePath = "c:\Users\taegyu\Codes\energyplus_project1\case_idf\case3_v3_KS\case3_v3_south.idf"
$targetPath = "c:\Users\taegyu\Codes\energyplus_project1\DSF_new\realscale\case3_v3_south_dsf_kinetic_bipv.idf"

$lines = [System.IO.File]::ReadAllLines($basePath)
$newLines = [System.Collections.Generic.List[string]]::new()

$winMatches = @{
    "BIPV_office_1_S..Wall_S_Glz0" = "Story1_Cavity_South_InnerWin";
    "BIPV_office_1_E..Wall_E_Glz0" = "Story1_Cavity_East_InnerWin";
    "BIPV_office_1_N..Wall_N_Glz0" = "Story1_Cavity_North_InnerWin";
    "BIPV_office_1_W..Wall_W_Glz0" = "Story1_Cavity_West_InnerWin";
    "BIPV_office_2_S..Wall_S_Glz0" = "Story2_Cavity_South_InnerWin";
    "BIPV_office_2_E..Wall_E_Glz0" = "Story2_Cavity_East_InnerWin";
    "BIPV_office_2_N..Wall_N_Glz0" = "Story2_Cavity_North_InnerWin";
    "BIPV_office_2_W..Wall_W_Glz0" = "Story2_Cavity_West_InnerWin";
}

$wallMatches = @{
    "BIPV_office_1_S..Wall_S" = "Story1_Cavity_South_InnerWall";
    "BIPV_office_1_E..Wall_E" = "Story1_Cavity_East_InnerWall";
    "BIPV_office_1_N..Wall_N" = "Story1_Cavity_North_InnerWall";
    "BIPV_office_1_W..Wall_W" = "Story1_Cavity_West_InnerWall";
    "BIPV_office_2_S..Wall_S" = "Story2_Cavity_South_InnerWall";
    "BIPV_office_2_E..Wall_E" = "Story2_Cavity_East_InnerWall";
    "BIPV_office_2_N..Wall_N" = "Story2_Cavity_North_InnerWall";
    "BIPV_office_2_W..Wall_W" = "Story2_Cavity_West_InnerWall";
}

$i = 0
while ($i -lt $lines.Length) {
    $line = $lines[$i]
    $trim = $line.Trim()

    # 1. Skip old Shading:Building:Detailed objects
    if ($trim.StartsWith("Shading:Building:Detailed,")) {
        while ($i -lt $lines.Length -and -not $lines[$i].Trim().EndsWith(";")) { $i++ }
        $i++
        continue
    }

    # 2. Skip old Generator:Photovoltaic objects
    if ($trim.StartsWith("Generator:Photovoltaic,")) {
        while ($i -lt $lines.Length -and -not $lines[$i].Trim().EndsWith(";")) { $i++ }
        $i++
        continue
    }

    # 3. Skip old PhotovoltaicPerformance objects
    if ($trim.StartsWith("PhotovoltaicPerformance:EquivalentOne-Diode,")) {
        while ($i -lt $lines.Length -and -not $lines[$i].Trim().EndsWith(";")) { $i++ }
        $i++
        continue
    }

    # 4. Skip old ElectricLoadCenter objects
    if ($trim.StartsWith("ElectricLoadCenter:Generators,") -or 
        $trim.StartsWith("ElectricLoadCenter:Inverter:Simple,") -or 
        $trim.StartsWith("ElectricLoadCenter:Distribution,")) {
        while ($i -lt $lines.Length -and -not $lines[$i].Trim().EndsWith(";")) { $i++ }
        $i++
        continue
    }

    # 5. Skip old PythonPlugin objects
    if ($trim.StartsWith("PythonPlugin:SearchPaths,") -or
        $trim.StartsWith("PythonPlugin:Instance,") -or 
        $trim.StartsWith("PythonPlugin:Variables,") -or 
        $trim.StartsWith("PythonPlugin:OutputVariable,")) {
        while ($i -lt $lines.Length -and -not $lines[$i].Trim().EndsWith(";")) { $i++ }
        $i++
        continue
    }

    # 6. Change Solar Distribution in Building object to FullExterior
    if ($trim.StartsWith("Building,")) {
        $bBlock = [System.Collections.Generic.List[string]]::new()
        while ($i -lt $lines.Length) {
            $bBlock.Add($lines[$i])
            if ($lines[$i].Trim().EndsWith(";")) { $i++; break }
            $i++
        }
        for ($k = 0; $k -lt $bBlock.Count; $k++) {
            if ($bBlock[$k].Contains("FullExteriorWithReflections")) {
                $bBlock[$k] = "    FullExterior,                 !- Solar Distribution"
            }
        }
        foreach ($b in $bBlock) { $newLines.Add($b) }
        continue
    }

    # 7. Modify 8 Windows on 4 Facades (1F & 2F) to point to Cavity InnerWin
    $matchedWin = $null
    foreach ($wKey in $winMatches.Keys) {
        if ($line.Contains($wKey + ",") -and $lines[$i+1].Contains("Window,")) {
            $matchedWin = $wKey
            break
        }
    }

    if ($matchedWin) {
        $targetWin = $winMatches[$matchedWin]
        $block = [System.Collections.Generic.List[string]]::new()
        while ($i -lt $lines.Length) {
            $block.Add($lines[$i])
            if ($lines[$i].Trim().EndsWith(";")) { $i++; break }
            $i++
        }
        # $block[0] is Name, $block[1] is Type, $block[2] is Construction, $block[3] is Surface Name, $block[4] is Boundary Object
        if ($block.Count -ge 5) {
            $block[4] = "    $targetWin,                   !- Outside Boundary Condition Object"
        }
        foreach ($b in $block) { $newLines.Add($b) }
        continue
    }

    # 8. Modify 8 Exterior Walls on 4 Facades (1F & 2F) to point to Cavity InnerWall
    $matchedWall = $null
    foreach ($wlKey in $wallMatches.Keys) {
        if ($line.Contains($wlKey + ",") -and $lines[$i+1].Contains("Wall,")) {
            $matchedWall = $wlKey
            break
        }
    }

    if ($matchedWall) {
        $targetWall = $wallMatches[$matchedWall]
        $block = [System.Collections.Generic.List[string]]::new()
        while ($i -lt $lines.Length) {
            $block.Add($lines[$i])
            if ($lines[$i].Trim().EndsWith(";")) { $i++; break }
            $i++
        }
        # $block[0] is Name, $block[1] is Wall, $block[2] is Constr, $block[3] is Zone, $block[4] is Space,
        # $block[5] is Outside Boundary Cond, $block[6] is Boundary Object, $block[7] is Sun, $block[8] is Wind
        if ($block.Count -ge 9) {
            $block[5] = "    Surface,                      !- Outside Boundary Condition"
            $block[6] = "    $targetWall,                  !- Outside Boundary Condition Object"
            $block[7] = "    NoSun,                        !- Sun Exposure"
            $block[8] = "    NoWind,                       !- Wind Exposure"
        }
        foreach ($b in $block) { $newLines.Add($b) }
        continue
    }

    $newLines.Add($line)
    $i++
}

# Function to create clean ZoneVentilation:DesignFlowRate blocks
function Get-VentBlock($name, $zone, $sched) {
    return @"
ZoneVentilation:DesignFlowRate,
    $name,
    $zone,
    $sched,
    AirChanges/Hour,
    ,
    ,
    ,
    20.0,
    Natural,
    ,
    ,
    1.0, 0.0, 0.0, 0.0,
    -100.0, , 100.0, , -100.0;
"@
}

$ventBlocks = [System.Text.StringBuilder]::new()
$ventBlocks.AppendLine("! ==============================================================================")
$ventBlocks.AppendLine("! DSF 2-DAMPER NATURAL VENTILATION SYSTEM (8 CAVITY ZONES, 20 ACH)")
$ventBlocks.AppendLine("! ==============================================================================")

$facadeNames = @("South", "East", "North", "West")
foreach ($fn in $facadeNames) {
    $ventBlocks.AppendLine((Get-VentBlock "Story1_Cavity_${fn}_BottomInletVent" "Zone_Story1_Cavity_${fn}" "DSF_Damper_TopBottom_Schedule"))
    $ventBlocks.AppendLine((Get-VentBlock "Story2_Cavity_${fn}_TopOutletVent"   "Zone_Story2_Cavity_${fn}" "DSF_Damper_TopBottom_Schedule"))
    $ventBlocks.AppendLine((Get-VentBlock "Story1_Cavity_${fn}_OuterLouverVent" "Zone_Story1_Cavity_${fn}" "DSF_Damper_OuterSkin_Schedule"))
    $ventBlocks.AppendLine((Get-VentBlock "Story2_Cavity_${fn}_OuterLouverVent" "Zone_Story2_Cavity_${fn}" "DSF_Damper_OuterSkin_Schedule"))
}

# Append complete 4-Facade DSF Cavity Zones, Surfaces, Glazing, 2-Damper Vents, and 40 BIPV Generators
$tail = @"

! ==============================================================================
! DSF 2-DAMPER SCHEDULE DEFINITIONS
! ==============================================================================
Schedule:Compact,
    DSF_Damper_TopBottom_Schedule,
    Fractional,
    Through: 12/31, For: AllDays, Until: 24:00, 0.0;

Schedule:Compact,
    DSF_Damper_OuterSkin_Schedule,
    Fractional,
    Through: 12/31, For: AllDays, Until: 24:00, 0.0;

! ==============================================================================
! 8 DSF CAVITY ZONES (4 FACADES x 2 FLOORS)
! ==============================================================================
Zone, Zone_Story1_Cavity_South, 0.0, 0,0,0, 1, 1, 4.0, 102.4, 25.6, Simple;
Zone, Zone_Story2_Cavity_South, 0.0, 0,0,0, 1, 1, 4.0, 102.4, 25.6, Simple;
Zone, Zone_Story1_Cavity_East,  0.0, 0,0,0, 1, 1, 4.0,  57.6, 14.4, Simple;
Zone, Zone_Story2_Cavity_East,  0.0, 0,0,0, 1, 1, 4.0,  57.6, 14.4, Simple;
Zone, Zone_Story1_Cavity_North, 0.0, 0,0,0, 1, 1, 4.0, 102.4, 25.6, Simple;
Zone, Zone_Story2_Cavity_North, 0.0, 0,0,0, 1, 1, 4.0, 102.4, 25.6, Simple;
Zone, Zone_Story1_Cavity_West,  0.0, 0,0,0, 1, 1, 4.0,  57.6, 14.4, Simple;
Zone, Zone_Story2_Cavity_West,  0.0, 0,0,0, 1, 1, 4.0,  57.6, 14.4, Simple;

! ==============================================================================
! DSF GLAZING MATERIAL & CONSTRUCTION (STPV 20% Transmittance)
! ==============================================================================
WindowMaterial:SimpleGlazingSystem,
    DSF_LowE_Glass_Material,
    1.50,                     !- U-Factor {W/m2-K}
    0.20,                     !- Solar Heat Gain Coefficient (20% Transmittance STPV)
    0.30;                     !- Visible Transmittance (30% VT)

Construction,
    DSF_Outer_LowE_Glazing,
    DSF_LowE_Glass_Material;

! ==============================================================================
! DSF CAVITY BUILDING SURFACES (4 FACADES x 2 FLOORS)
! ==============================================================================

! --- SOUTH CAVITY 1F & 2F ---
BuildingSurface:Detailed, Story1_Cavity_South_Floor, Floor, Generic Ground Slab, Zone_Story1_Cavity_South, , Ground, , NoSun, NoWind, 1.0, 4,
    0.0, 0.0, 0.0, 32.0, 0.0, 0.0, 32.0, -0.8, 0.0, 0.0, -0.8, 0.0;
BuildingSurface:Detailed, Story1_Cavity_South_InnerWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_South, , Surface, BIPV_office_1_S..Wall_S, NoSun, NoWind, 1.0, 4,
    32.0, 0.0, 4.0, 32.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_South_OuterWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, -0.8, 4.0, 0.0, -0.8, 0.0, 32.0, -0.8, 0.0, 32.0, -0.8, 4.0;
BuildingSurface:Detailed, Story1_Cavity_South_WestWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 0.0, 4.0, 0.0, 0.0, 0.0, 0.0, -0.8, 0.0, 0.0, -0.8, 4.0;
BuildingSurface:Detailed, Story1_Cavity_South_EastWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, -0.8, 4.0, 32.0, -0.8, 0.0, 32.0, 0.0, 0.0, 32.0, 0.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_South_Ceiling, Ceiling, Generic Interior Ceiling, Zone_Story1_Cavity_South, , Surface, Story2_Cavity_South_Floor, NoSun, NoWind, 1.0, 4,
    0.0, -0.8, 4.0, 32.0, -0.8, 4.0, 32.0, 0.0, 4.0, 0.0, 0.0, 4.0;

BuildingSurface:Detailed, Story2_Cavity_South_Floor, Floor, Generic Interior Floor, Zone_Story2_Cavity_South, , Surface, Story1_Cavity_South_Ceiling, NoSun, NoWind, 1.0, 4,
    0.0, 0.0, 4.0, 32.0, 0.0, 4.0, 32.0, -0.8, 4.0, 0.0, -0.8, 4.0;
BuildingSurface:Detailed, Story2_Cavity_South_InnerWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_South, , Surface, BIPV_office_2_S..Wall_S, NoSun, NoWind, 1.0, 4,
    32.0, 0.0, 8.0, 32.0, 0.0, 4.0, 0.0, 0.0, 4.0, 0.0, 0.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_South_OuterWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, -0.8, 8.0, 0.0, -0.8, 4.0, 32.0, -0.8, 4.0, 32.0, -0.8, 8.0;
BuildingSurface:Detailed, Story2_Cavity_South_WestWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 0.0, 8.0, 0.0, 0.0, 4.0, 0.0, -0.8, 4.0, 0.0, -0.8, 8.0;
BuildingSurface:Detailed, Story2_Cavity_South_EastWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, -0.8, 8.0, 32.0, -0.8, 4.0, 32.0, 0.0, 4.0, 32.0, 0.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_South_Roof, Roof, Generic Roof, Zone_Story2_Cavity_South, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, -0.8, 8.0, 32.0, -0.8, 8.0, 32.0, 0.0, 8.0, 0.0, 0.0, 8.0;

! --- EAST CAVITY 1F & 2F ---
BuildingSurface:Detailed, Story1_Cavity_East_Floor, Floor, Generic Ground Slab, Zone_Story1_Cavity_East, , Ground, , NoSun, NoWind, 1.0, 4,
    32.0, 0.0, 0.0, 32.0, 18.0, 0.0, 32.8, 18.0, 0.0, 32.8, 0.0, 0.0;
BuildingSurface:Detailed, Story1_Cavity_East_InnerWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_East, , Surface, BIPV_office_1_E..Wall_E, NoSun, NoWind, 1.0, 4,
    32.0, 18.0, 4.0, 32.0, 18.0, 0.0, 32.0, 0.0, 0.0, 32.0, 0.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_East_OuterWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.8, 0.0, 4.0, 32.8, 0.0, 0.0, 32.8, 18.0, 0.0, 32.8, 18.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_East_SouthWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 0.0, 4.0, 32.0, 0.0, 0.0, 32.8, 0.0, 0.0, 32.8, 0.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_East_NorthWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.8, 18.0, 4.0, 32.8, 18.0, 0.0, 32.0, 18.0, 0.0, 32.0, 18.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_East_Ceiling, Ceiling, Generic Interior Ceiling, Zone_Story1_Cavity_East, , Surface, Story2_Cavity_East_Floor, NoSun, NoWind, 1.0, 4,
    32.0, 0.0, 4.0, 32.8, 0.0, 4.0, 32.8, 18.0, 4.0, 32.0, 18.0, 4.0;

BuildingSurface:Detailed, Story2_Cavity_East_Floor, Floor, Generic Interior Floor, Zone_Story2_Cavity_East, , Surface, Story1_Cavity_East_Ceiling, NoSun, NoWind, 1.0, 4,
    32.0, 0.0, 4.0, 32.0, 18.0, 4.0, 32.8, 18.0, 4.0, 32.8, 0.0, 4.0;
BuildingSurface:Detailed, Story2_Cavity_East_InnerWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_East, , Surface, BIPV_office_2_E..Wall_E, NoSun, NoWind, 1.0, 4,
    32.0, 18.0, 8.0, 32.0, 18.0, 4.0, 32.0, 0.0, 4.0, 32.0, 0.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_East_OuterWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.8, 0.0, 8.0, 32.8, 0.0, 4.0, 32.8, 18.0, 4.0, 32.8, 18.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_East_SouthWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 0.0, 8.0, 32.0, 0.0, 4.0, 32.8, 0.0, 4.0, 32.8, 0.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_East_NorthWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.8, 18.0, 8.0, 32.8, 18.0, 4.0, 32.0, 18.0, 4.0, 32.0, 18.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_East_Roof, Roof, Generic Roof, Zone_Story2_Cavity_East, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 0.0, 8.0, 32.8, 0.0, 8.0, 32.8, 18.0, 8.0, 32.0, 18.0, 8.0;

! --- NORTH CAVITY 1F & 2F ---
BuildingSurface:Detailed, Story1_Cavity_North_Floor, Floor, Generic Ground Slab, Zone_Story1_Cavity_North, , Ground, , NoSun, NoWind, 1.0, 4,
    32.0, 18.0, 0.0, 0.0, 18.0, 0.0, 0.0, 18.8, 0.0, 32.0, 18.8, 0.0;
BuildingSurface:Detailed, Story1_Cavity_North_InnerWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_North, , Surface, BIPV_office_1_N..Wall_N, NoSun, NoWind, 1.0, 4,
    0.0, 18.0, 4.0, 0.0, 18.0, 0.0, 32.0, 18.0, 0.0, 32.0, 18.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_North_OuterWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 18.8, 4.0, 32.0, 18.8, 0.0, 0.0, 18.8, 0.0, 0.0, 18.8, 4.0;
BuildingSurface:Detailed, Story1_Cavity_North_EastWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 18.0, 4.0, 32.0, 18.0, 0.0, 32.0, 18.8, 0.0, 32.0, 18.8, 4.0;
BuildingSurface:Detailed, Story1_Cavity_North_WestWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 18.8, 4.0, 0.0, 18.8, 0.0, 0.0, 18.0, 0.0, 0.0, 18.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_North_Ceiling, Ceiling, Generic Interior Ceiling, Zone_Story1_Cavity_North, , Surface, Story2_Cavity_North_Floor, NoSun, NoWind, 1.0, 4,
    0.0, 18.8, 4.0, 32.0, 18.8, 4.0, 32.0, 18.0, 4.0, 0.0, 18.0, 4.0;

BuildingSurface:Detailed, Story2_Cavity_North_Floor, Floor, Generic Interior Floor, Zone_Story2_Cavity_North, , Surface, Story1_Cavity_North_Ceiling, NoSun, NoWind, 1.0, 4,
    32.0, 18.0, 4.0, 0.0, 18.0, 4.0, 0.0, 18.8, 4.0, 32.0, 18.8, 4.0;
BuildingSurface:Detailed, Story2_Cavity_North_InnerWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_North, , Surface, BIPV_office_2_N..Wall_N, NoSun, NoWind, 1.0, 4,
    0.0, 18.0, 8.0, 0.0, 18.0, 4.0, 32.0, 18.0, 4.0, 32.0, 18.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_North_OuterWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 18.8, 8.0, 32.0, 18.8, 4.0, 0.0, 18.8, 4.0, 0.0, 18.8, 8.0;
BuildingSurface:Detailed, Story2_Cavity_North_EastWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    32.0, 18.0, 8.0, 32.0, 18.0, 4.0, 32.0, 18.8, 4.0, 32.0, 18.8, 8.0;
BuildingSurface:Detailed, Story2_Cavity_North_WestWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 18.8, 8.0, 0.0, 18.8, 4.0, 0.0, 18.0, 4.0, 0.0, 18.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_North_Roof, Roof, Generic Roof, Zone_Story2_Cavity_North, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 18.0, 8.0, 32.0, 18.0, 8.0, 32.0, 18.8, 8.0, 0.0, 18.8, 8.0;

! --- WEST CAVITY 1F & 2F ---
BuildingSurface:Detailed, Story1_Cavity_West_Floor, Floor, Generic Ground Slab, Zone_Story1_Cavity_West, , Ground, , NoSun, NoWind, 1.0, 4,
    0.0, 18.0, 0.0, 0.0, 0.0, 0.0, -0.8, 0.0, 0.0, -0.8, 18.0, 0.0;
BuildingSurface:Detailed, Story1_Cavity_West_InnerWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_West, , Surface, BIPV_office_1_W..Wall_W, NoSun, NoWind, 1.0, 4,
    0.0, 0.0, 4.0, 0.0, 0.0, 0.0, 0.0, 18.0, 0.0, 0.0, 18.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_West_OuterWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    -0.8, 18.0, 4.0, -0.8, 18.0, 0.0, -0.8, 0.0, 0.0, -0.8, 0.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_West_NorthWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 18.0, 4.0, 0.0, 18.0, 0.0, -0.8, 18.0, 0.0, -0.8, 18.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_West_SouthWall, Wall, Generic Exterior Wall, Zone_Story1_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    -0.8, 0.0, 4.0, -0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0;
BuildingSurface:Detailed, Story1_Cavity_West_Ceiling, Ceiling, Generic Interior Ceiling, Zone_Story1_Cavity_West, , Surface, Story2_Cavity_West_Floor, NoSun, NoWind, 1.0, 4,
    0.0, 18.0, 4.0, -0.8, 18.0, 4.0, -0.8, 0.0, 4.0, 0.0, 0.0, 4.0;

BuildingSurface:Detailed, Story2_Cavity_West_Floor, Floor, Generic Interior Floor, Zone_Story2_Cavity_West, , Surface, Story1_Cavity_West_Ceiling, NoSun, NoWind, 1.0, 4,
    0.0, 18.0, 4.0, 0.0, 0.0, 4.0, -0.8, 0.0, 4.0, -0.8, 18.0, 4.0;
BuildingSurface:Detailed, Story2_Cavity_West_InnerWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_West, , Surface, BIPV_office_2_W..Wall_W, NoSun, NoWind, 1.0, 4,
    0.0, 0.0, 8.0, 0.0, 0.0, 4.0, 0.0, 18.0, 4.0, 0.0, 18.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_West_OuterWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    -0.8, 18.0, 8.0, -0.8, 18.0, 4.0, -0.8, 0.0, 4.0, -0.8, 0.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_West_NorthWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 18.0, 8.0, 0.0, 18.0, 4.0, -0.8, 18.0, 4.0, -0.8, 18.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_West_SouthWall, Wall, Generic Exterior Wall, Zone_Story2_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    -0.8, 0.0, 8.0, -0.8, 0.0, 4.0, 0.0, 0.0, 4.0, 0.0, 0.0, 8.0;
BuildingSurface:Detailed, Story2_Cavity_West_Roof, Roof, Generic Roof, Zone_Story2_Cavity_West, , Outdoors, , SunExposed, WindExposed, 1.0, 4,
    0.0, 18.0, 8.0, -0.8, 18.0, 8.0, -0.8, 0.0, 8.0, 0.0, 0.0, 8.0;

! ==============================================================================
! DSF INNER & OUTER GLASS FENESTRATION SURFACES (4 FACADES x 2 FLOORS)
! ==============================================================================
! 1F Inner Windows
FenestrationSurface:Detailed, Story1_Cavity_South_InnerWin, Window, Generic Double Pane, Story1_Cavity_South_InnerWall, BIPV_office_1_S..Wall_S_Glz0, , , 1.0, 4,
    31.68, 0.0, 3.96, 31.68, 0.0, 0.28653, 0.32, 0.0, 0.28653, 0.32, 0.0, 3.96;
FenestrationSurface:Detailed, Story1_Cavity_East_InnerWin, Window, Generic Double Pane, Story1_Cavity_East_InnerWall, BIPV_office_1_E..Wall_E_Glz0, , , 1.0, 4,
    32.0, 17.82, 3.96, 32.0, 17.82, 0.28653, 32.0, 0.18, 0.28653, 32.0, 0.18, 3.96;
FenestrationSurface:Detailed, Story1_Cavity_North_InnerWin, Window, Generic Double Pane, Story1_Cavity_North_InnerWall, BIPV_office_1_N..Wall_N_Glz0, , , 1.0, 4,
    0.32, 18.0, 3.96, 0.32, 18.0, 0.28653, 31.68, 18.0, 0.28653, 31.68, 18.0, 3.96;
FenestrationSurface:Detailed, Story1_Cavity_West_InnerWin, Window, Generic Double Pane, Story1_Cavity_West_InnerWall, BIPV_office_1_W..Wall_W_Glz0, , , 1.0, 4,
    0.0, 0.18, 3.96, 0.0, 0.18, 0.28653, 0.0, 17.82, 0.28653, 0.0, 17.82, 3.96;

! 2F Inner Windows
FenestrationSurface:Detailed, Story2_Cavity_South_InnerWin, Window, Generic Double Pane, Story2_Cavity_South_InnerWall, BIPV_office_2_S..Wall_S_Glz0, , , 1.0, 4,
    31.68, 0.0, 7.96, 31.68, 0.0, 4.28653, 0.32, 0.0, 4.28653, 0.32, 0.0, 7.96;
FenestrationSurface:Detailed, Story2_Cavity_East_InnerWin, Window, Generic Double Pane, Story2_Cavity_East_InnerWall, BIPV_office_2_E..Wall_E_Glz0, , , 1.0, 4,
    32.0, 17.82, 7.96, 32.0, 17.82, 4.28653, 32.0, 0.18, 4.28653, 32.0, 0.18, 7.96;
FenestrationSurface:Detailed, Story2_Cavity_North_InnerWin, Window, Generic Double Pane, Story2_Cavity_North_InnerWall, BIPV_office_2_N..Wall_N_Glz0, , , 1.0, 4,
    0.32, 18.0, 7.96, 0.32, 18.0, 4.28653, 31.68, 18.0, 4.28653, 31.68, 18.0, 7.96;
FenestrationSurface:Detailed, Story2_Cavity_West_InnerWin, Window, Generic Double Pane, Story2_Cavity_West_InnerWall, BIPV_office_2_W..Wall_W_Glz0, , , 1.0, 4,
    0.0, 0.18, 7.96, 0.0, 0.18, 4.28653, 0.0, 17.82, 4.28653, 0.0, 17.82, 7.96;

! 1F Outer Glass
FenestrationSurface:Detailed, Story1_Cavity_South_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story1_Cavity_South_OuterWall, , , , 1.0, 4,
    0.32, -0.8, 3.96, 0.32, -0.8, 0.28653, 31.68, -0.8, 0.28653, 31.68, -0.8, 3.96;
FenestrationSurface:Detailed, Story1_Cavity_East_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story1_Cavity_East_OuterWall, , , , 1.0, 4,
    32.8, 0.18, 3.96, 32.8, 0.18, 0.28653, 32.8, 17.82, 0.28653, 32.8, 17.82, 3.96;
FenestrationSurface:Detailed, Story1_Cavity_North_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story1_Cavity_North_OuterWall, , , , 1.0, 4,
    31.68, 18.8, 3.96, 31.68, 18.8, 0.28653, 0.32, 18.8, 0.28653, 0.32, 18.8, 3.96;
FenestrationSurface:Detailed, Story1_Cavity_West_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story1_Cavity_West_OuterWall, , , , 1.0, 4,
    -0.8, 17.82, 3.96, -0.8, 17.82, 0.28653, -0.8, 0.18, 0.28653, -0.8, 0.18, 3.96;

! 2F Outer Glass
FenestrationSurface:Detailed, Story2_Cavity_South_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story2_Cavity_South_OuterWall, , , , 1.0, 4,
    0.32, -0.8, 7.96, 0.32, -0.8, 4.28653, 31.68, -0.8, 4.28653, 31.68, -0.8, 7.96;
FenestrationSurface:Detailed, Story2_Cavity_East_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story2_Cavity_East_OuterWall, , , , 1.0, 4,
    32.8, 0.18, 7.96, 32.8, 0.18, 4.28653, 32.8, 17.82, 4.28653, 32.8, 17.82, 7.96;
FenestrationSurface:Detailed, Story2_Cavity_North_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story2_Cavity_North_OuterWall, , , , 1.0, 4,
    31.68, 18.8, 7.96, 31.68, 18.8, 4.28653, 0.32, 18.8, 4.28653, 0.32, 18.8, 7.96;
FenestrationSurface:Detailed, Story2_Cavity_West_OuterGlass, Window, DSF_Outer_LowE_Glazing, Story2_Cavity_West_OuterWall, , , , 1.0, 4,
    -0.8, 17.82, 7.96, -0.8, 17.82, 4.28653, -0.8, 0.18, 4.28653, -0.8, 0.18, 7.96;

! ==============================================================================
! HIGH-FIDELITY EQUIVALENT ONE-DIODE PERFORMANCE (Shinsung SolarSkin 390W)
! ==============================================================================
PhotovoltaicPerformance:EquivalentOne-Diode,
    Shinsung_SolarSkin_390W_Performance,  !- Name
    CrystallineSilicon,           !- Cell type
    66,                           !- Number of Cells in Series
    2.186184,                     !- Active Area {m2}
    0.85,                         !- Transmittance Absorptance Product
    1.12,                         !- Semiconductor Bandgap {eV}
    500.0,                        !- Shunt Resistance {ohms}
    10.42,                        !- Short Circuit Current {A}
    46.64,                        !- Open Circuit Voltage {V}
    25,                           !- Reference Temperature {C}
    1000,                         !- Reference Insolation {W/m2}
    9.99,                         !- Module Current at Maximum Power {A}
    39.11,                        !- Module Voltage at Maximum Power {V}
    0.006252,                     !- Temperature Coefficient of Short Circuit Current {A/K}
    -0.139920,                    !- Temperature Coefficient of Open Circuit Voltage {V/K}
    20,                           !- Nominal Operating Cell Temperature Test Ambient Temperature {C}
    45.0,                         !- Nominal Operating Cell Temperature Test Cell Temperature {C}
    800,                          !- Nominal Operating Cell Temperature Test Insolation {W/m2}
    80.0,                         !- Module Heat Loss Coefficient {W/m2-K}
    50000;                        !- Maximum Power Point Tracking Voltage {V}

! ==============================================================================
! 40 KINETIC BIPV CANDIDATE GENERATORS ON 4 FACADES (10 ANGLES x 4 FACADES)
! ==============================================================================
! South Facade (Gross 230.4 m2, Factor 84.3113)
Generator:Photovoltaic, Generator_BIPV_South_A00, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A10, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A20, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A30, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A40, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A50, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A60, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A70, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A80, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_South_A90, Story1_Cavity_South_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;

! East Facade (Gross 129.6 m2, Factor 47.4251)
Generator:Photovoltaic, Generator_BIPV_East_A00, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A10, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A20, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A30, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A40, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A50, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A60, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A70, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A80, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_East_A90, Story1_Cavity_East_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;

! North Facade (Gross 230.4 m2, Factor 84.3113)
Generator:Photovoltaic, Generator_BIPV_North_A00, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A10, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A20, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A30, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A40, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A50, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A60, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A70, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A80, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;
Generator:Photovoltaic, Generator_BIPV_North_A90, Story1_Cavity_North_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 84.3113, 1.0;

! West Facade (Gross 129.6 m2, Factor 47.4251)
Generator:Photovoltaic, Generator_BIPV_West_A00, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A10, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A20, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A30, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A40, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A50, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A60, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A70, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A80, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;
Generator:Photovoltaic, Generator_BIPV_West_A90, Story1_Cavity_West_OuterGlass, PhotovoltaicPerformance:EquivalentOne-Diode, Shinsung_SolarSkin_390W_Performance, Decoupled, 47.4251, 1.0;

! ==============================================================================
! ELECTRIC LOAD CENTER & INVERTER SYSTEM (40 GENERATORS)
! ==============================================================================
ElectricLoadCenter:Generators,
    Kinetic_BIPV_Generator_List,
    Generator_BIPV_South_A00, Generator:Photovoltaic, 500000, AvailSched_BIPV_A00, ,
    Generator_BIPV_South_A10, Generator:Photovoltaic, 500000, AvailSched_BIPV_A10, ,
    Generator_BIPV_South_A20, Generator:Photovoltaic, 500000, AvailSched_BIPV_A20, ,
    Generator_BIPV_South_A30, Generator:Photovoltaic, 500000, AvailSched_BIPV_A30, ,
    Generator_BIPV_South_A40, Generator:Photovoltaic, 500000, AvailSched_BIPV_A40, ,
    Generator_BIPV_South_A50, Generator:Photovoltaic, 500000, AvailSched_BIPV_A50, ,
    Generator_BIPV_South_A60, Generator:Photovoltaic, 500000, AvailSched_BIPV_A60, ,
    Generator_BIPV_South_A70, Generator:Photovoltaic, 500000, AvailSched_BIPV_A70, ,
    Generator_BIPV_South_A80, Generator:Photovoltaic, 500000, AvailSched_BIPV_A80, ,
    Generator_BIPV_South_A90, Generator:Photovoltaic, 500000, AvailSched_BIPV_A90, ,
    Generator_BIPV_East_A00, Generator:Photovoltaic, 500000, AvailSched_BIPV_A00, ,
    Generator_BIPV_East_A10, Generator:Photovoltaic, 500000, AvailSched_BIPV_A10, ,
    Generator_BIPV_East_A20, Generator:Photovoltaic, 500000, AvailSched_BIPV_A20, ,
    Generator_BIPV_East_A30, Generator:Photovoltaic, 500000, AvailSched_BIPV_A30, ,
    Generator_BIPV_East_A40, Generator:Photovoltaic, 500000, AvailSched_BIPV_A40, ,
    Generator_BIPV_East_A50, Generator:Photovoltaic, 500000, AvailSched_BIPV_A50, ,
    Generator_BIPV_East_A60, Generator:Photovoltaic, 500000, AvailSched_BIPV_A60, ,
    Generator_BIPV_East_A70, Generator:Photovoltaic, 500000, AvailSched_BIPV_A70, ,
    Generator_BIPV_East_A80, Generator:Photovoltaic, 500000, AvailSched_BIPV_A80, ,
    Generator_BIPV_East_A90, Generator:Photovoltaic, 500000, AvailSched_BIPV_A90, ,
    Generator_BIPV_North_A00, Generator:Photovoltaic, 500000, AvailSched_BIPV_A00, ,
    Generator_BIPV_North_A10, Generator:Photovoltaic, 500000, AvailSched_BIPV_A10, ,
    Generator_BIPV_North_A20, Generator:Photovoltaic, 500000, AvailSched_BIPV_A20, ,
    Generator_BIPV_North_A30, Generator:Photovoltaic, 500000, AvailSched_BIPV_A30, ,
    Generator_BIPV_North_A40, Generator:Photovoltaic, 500000, AvailSched_BIPV_A40, ,
    Generator_BIPV_North_A50, Generator:Photovoltaic, 500000, AvailSched_BIPV_A50, ,
    Generator_BIPV_North_A60, Generator:Photovoltaic, 500000, AvailSched_BIPV_A60, ,
    Generator_BIPV_North_A70, Generator:Photovoltaic, 500000, AvailSched_BIPV_A70, ,
    Generator_BIPV_North_A80, Generator:Photovoltaic, 500000, AvailSched_BIPV_A80, ,
    Generator_BIPV_North_A90, Generator:Photovoltaic, 500000, AvailSched_BIPV_A90, ,
    Generator_BIPV_West_A00, Generator:Photovoltaic, 500000, AvailSched_BIPV_A00, ,
    Generator_BIPV_West_A10, Generator:Photovoltaic, 500000, AvailSched_BIPV_A10, ,
    Generator_BIPV_West_A20, Generator:Photovoltaic, 500000, AvailSched_BIPV_A20, ,
    Generator_BIPV_West_A30, Generator:Photovoltaic, 500000, AvailSched_BIPV_A30, ,
    Generator_BIPV_West_A40, Generator:Photovoltaic, 500000, AvailSched_BIPV_A40, ,
    Generator_BIPV_West_A50, Generator:Photovoltaic, 500000, AvailSched_BIPV_A50, ,
    Generator_BIPV_West_A60, Generator:Photovoltaic, 500000, AvailSched_BIPV_A60, ,
    Generator_BIPV_West_A70, Generator:Photovoltaic, 500000, AvailSched_BIPV_A70, ,
    Generator_BIPV_West_A80, Generator:Photovoltaic, 500000, AvailSched_BIPV_A80, ,
    Generator_BIPV_West_A90, Generator:Photovoltaic, 500000, AvailSched_BIPV_A90, ;

ElectricLoadCenter:Inverter:Simple,
    Kinetic_BIPV_Inverter,
    ,
    ,
    0.10,
    0.96;

ElectricLoadCenter:Distribution,
    Kinetic_BIPV_ElectricLoadCenter,
    Kinetic_BIPV_Generator_List,
    Baseload,
    0,
    ,
    ,
    DirectCurrentWithInverter,
    Kinetic_BIPV_Inverter;

! ==============================================================================
! PYTHON PLUGIN INTEGRATION FOR COUPLED KINETIC BIPV & DSF CONTROL
! ==============================================================================
PythonPlugin:SearchPaths,
    Yes,                          !- Add Current Working Directory to Search Path
    Yes,                          !- Add Input File Directory to Search Path
    ;

PythonPlugin:Instance,
    DSFKineticBIPVRealscalePlugin,!- Name
    Yes,                          !- Run During Warmup Days
    dsf_kinetic_bipv_realscale_plugin, !- Module Name
    DSFKineticBIPVRealscalePlugin;!- Class Name

PythonPlugin:Variables,
    BIPV_Vars,                    !- Name
    BIPV_Tilt_Angle,              !- Variable Name 1
    DSF_Damper_Opening,           !- Variable Name 2
    DSF_Operating_Mode,           !- Variable Name 3
    BIPV_Incident_Solar,          !- Variable Name 4
    BIPV_Power_Generation,        !- Variable Name 5
    BIPV_Efficiency;              !- Variable Name 6

PythonPlugin:OutputVariable,
    BIPV_Tilt_Angle,
    BIPV_Tilt_Angle,
    Averaged,
    ZoneTimestep,
    deg;

PythonPlugin:OutputVariable,
    DSF_Damper_Opening,
    DSF_Damper_Opening,
    Averaged,
    ZoneTimestep,
    ;

PythonPlugin:OutputVariable,
    DSF_Operating_Mode,
    DSF_Operating_Mode,
    Averaged,
    ZoneTimestep,
    ;

PythonPlugin:OutputVariable,
    BIPV_Incident_Solar,
    BIPV_Incident_Solar,
    Averaged,
    ZoneTimestep,
    W/m2;

PythonPlugin:OutputVariable,
    BIPV_Efficiency,
    BIPV_Efficiency,
    Averaged,
    ZoneTimestep,
    ;

Output:Variable, *, Generator Produced DC Electricity Energy, Timestep;
Output:Variable, *, Inverter Electricity Production Energy, Timestep;
Output:Variable, *, Generator Produced DC Electricity Rate, Timestep;
Output:Variable, *, Generator PV Array Efficiency, Timestep;
Output:Variable, *, Zone Ventilation Current Density Volume Flow Rate, Timestep;
Output:Variable, *, Zone Ventilation Mass Flow Rate, Timestep;

"@

$finalContent = [string]::Join("`r`n", $newLines) + "`r`n" + $tail + "`r`n" + $ventBlocks.ToString()
[System.IO.File]::WriteAllText($targetPath, $finalContent, [System.Text.Encoding]::UTF8)
Write-Host "Successfully generated corrected 4-Facade Real-Scale DSF + Kinetic BIPV model!"
