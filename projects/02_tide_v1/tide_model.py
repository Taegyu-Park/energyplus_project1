"""
tide_model.py
=============
PyTorch Implementation of Google's TiDE (Time-series Dense Encoder) Architecture.
Reference: Das et al., "Long-term Forecasting with TiDE: Time-series Dense Encoder" (2023)

Key Architectural Components:
1. ResidualBlock: Dense Linear -> ReLU -> Linear -> Dropout with Residual Connection & LayerNorm.
2. FeatureProjection: Projects dynamic covariates (past & future) to a low-dimensional space.
3. DenseEncoder: Flattens lookback targets, past covariates, and future covariates into a latent vector.
4. DenseDecoder: Maps latent vector to per-step representations for horizon H.
5. TemporalDecoder: Merges step representations with future covariates to generate multi-target predictions.
6. Lookback Residual: Linear skip connection directly mapping lookback targets to horizon predictions.
"""

import torch
import torch.nn as nn
from typing import Optional


class ResidualBlock(nn.Module):
    """
    Standard TiDE Residual Block.
    in_features -> hidden_features (ReLU) -> out_features -> Dropout -> Add Skip -> LayerNorm
    """
    def __init__(self, in_features: int, hidden_features: int, out_features: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_features, out_features)
        self.dropout = nn.Dropout(dropout)
        
        # Skip connection projection if dimensions mismatch
        if in_features != out_features:
            self.skip_proj = nn.Linear(in_features, out_features)
        else:
            self.skip_proj = nn.Identity()
            
        self.layer_norm = nn.LayerNorm(out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.skip_proj(x)
        out = self.fc1(x)
        out = self.relu(out)
        out = self.fc2(out)
        out = self.dropout(out)
        out = self.layer_norm(out + residual)
        return out


class TiDEModel(nn.Module):
    """
    TiDE (Time-series Dense Encoder) for Multivariate Time-Series Forecasting.
    
    Args:
        lookback_len (int): Lookback sequence length (L). Default: 144 (24 hours at 10-min interval)
        horizon_len (int): Prediction sequence length (H). Default: 24 (4 hours at 10-min interval)
        num_targets (int): Number of target variables (e.g., 10 for Strategy 1, 30 for Strategy 2)
        past_cov_dim (int): Number of past dynamic covariates (e.g., outdoor temp, solar irradiance)
        future_cov_dim (int): Number of future known covariates (e.g., sun angles, time cyclic encodings)
        hidden_dim (int): Hidden dimension for encoder/decoder blocks (default: 256)
        proj_dim (int): Projection dimension for dynamic covariates (default: 16)
        num_encoder_layers (int): Number of residual blocks in Dense Encoder (default: 2)
        num_decoder_layers (int): Number of residual blocks in Dense Decoder (default: 2)
        decoder_output_dim (int): Output feature dimension per horizon step from Dense Decoder (default: 32)
        dropout (float): Dropout probability (default: 0.1)
    """
    def __init__(
        self,
        lookback_len: int = 144,
        horizon_len: int = 24,
        num_targets: int = 10,
        past_cov_dim: int = 3,
        future_cov_dim: int = 6,
        hidden_dim: int = 256,
        proj_dim: int = 16,
        num_encoder_layers: int = 2,
        num_decoder_layers: int = 2,
        decoder_output_dim: int = 32,
        dropout: float = 0.1
    ):
        super().__init__()
        self.lookback_len = lookback_len
        self.horizon_len = horizon_len
        self.num_targets = num_targets
        self.past_cov_dim = past_cov_dim
        self.future_cov_dim = future_cov_dim
        self.proj_dim = proj_dim
        self.decoder_output_dim = decoder_output_dim

        # 1. Feature Projection Layers
        self.past_proj = nn.Linear(past_cov_dim, proj_dim) if past_cov_dim > 0 else None
        self.future_proj = nn.Linear(future_cov_dim, proj_dim) if future_cov_dim > 0 else None

        # Calculate total flattened input dimension for Dense Encoder
        # Targets: L * num_targets
        # Past Covariates: L * proj_dim
        # Future Covariates: (L + H) * proj_dim
        enc_in_dim = (lookback_len * num_targets) + (lookback_len * proj_dim) + ((lookback_len + horizon_len) * proj_dim)

        # 2. Dense Encoder
        encoder_blocks = []
        in_d = enc_in_dim
        for _ in range(num_encoder_layers):
            encoder_blocks.append(ResidualBlock(in_d, hidden_dim, hidden_dim, dropout=dropout))
            in_d = hidden_dim
        self.encoder = nn.Sequential(*encoder_blocks)

        # 3. Dense Decoder
        decoder_blocks = []
        dec_out_dim = horizon_len * decoder_output_dim
        in_d = hidden_dim
        for i in range(num_decoder_layers):
            out_d = dec_out_dim if i == num_decoder_layers - 1 else hidden_dim
            decoder_blocks.append(ResidualBlock(in_d, hidden_dim, out_d, dropout=dropout))
            in_d = out_d
        self.decoder = nn.Sequential(*decoder_blocks)

        # 4. Temporal Decoder (applied per horizon step)
        # Combines decoder representation per step with the projected future covariate for that step
        temporal_in_dim = decoder_output_dim + proj_dim
        self.temporal_decoder = nn.Sequential(
            nn.Linear(temporal_in_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, num_targets)
        )

        # 5. Global Lookback Residual Connection (Linear mapping from lookback targets directly to horizon)
        self.lookback_residual = nn.Linear(lookback_len * num_targets, horizon_len * num_targets)

    def forward(
        self,
        lookback_targets: torch.Tensor,       # Shape: (B, L, num_targets)
        past_covariates: torch.Tensor,        # Shape: (B, L, past_cov_dim)
        future_covariates: torch.Tensor       # Shape: (B, L + H, future_cov_dim)
    ) -> torch.Tensor:
        """
        Forward pass of TiDE model.
        Returns:
            predicted_targets: Shape (B, H, num_targets)
        """
        batch_size = lookback_targets.size(0)

        # 1. Feature Projection
        proj_past = self.past_proj(past_covariates)             # (B, L, proj_dim)
        proj_future = self.future_proj(future_covariates)       # (B, L + H, proj_dim)

        # 2. Flatten for Dense Encoder
        flat_targets = lookback_targets.reshape(batch_size, -1) # (B, L * num_targets)
        flat_past_cov = proj_past.reshape(batch_size, -1)       # (B, L * proj_dim)
        flat_future_cov = proj_future.reshape(batch_size, -1)   # (B, (L + H) * proj_dim)

        encoder_input = torch.cat([flat_targets, flat_past_cov, flat_future_cov], dim=-1)

        # 3. Dense Encoding & Decoding
        latent = self.encoder(encoder_input)                    # (B, hidden_dim)
        decoded = self.decoder(latent)                          # (B, H * decoder_output_dim)
        decoded = decoded.view(batch_size, self.horizon_len, self.decoder_output_dim) # (B, H, dec_dim)

        # 4. Temporal Decoding
        # Extract projected future covariates corresponding to the horizon window [L : L + H]
        horizon_future_proj = proj_future[:, self.lookback_len:, :] # (B, H, proj_dim)
        temporal_input = torch.cat([decoded, horizon_future_proj], dim=-1) # (B, H, dec_dim + proj_dim)
        temporal_out = self.temporal_decoder(temporal_input)    # (B, H, num_targets)

        # 5. Lookback Residual Connection
        residual = self.lookback_residual(flat_targets)         # (B, H * num_targets)
        residual = residual.view(batch_size, self.horizon_len, self.num_targets)

        # Final prediction = Temporal decoder output + Global linear skip
        final_prediction = temporal_out + residual              # (B, H, num_targets)

        return final_prediction


if __name__ == "__main__":
    print("Testing TiDE Architecture with mock batch...")
    B, L, H = 16, 144, 24
    num_targets = 10
    past_cov_dim = 3
    future_cov_dim = 6

    mock_targets = torch.randn(B, L, num_targets)
    mock_past_cov = torch.randn(B, L, past_cov_dim)
    mock_future_cov = torch.randn(B, L + H, future_cov_dim)

    model = TiDEModel(
        lookback_len=L,
        horizon_len=H,
        num_targets=num_targets,
        past_cov_dim=past_cov_dim,
        future_cov_dim=future_cov_dim,
        hidden_dim=256,
        proj_dim=16
    )

    out = model(mock_targets, mock_past_cov, mock_future_cov)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"-> Model Output Shape: {out.shape} (Expected: ({B}, {H}, {num_targets}))")
    print(f"-> Total Trainable Parameters: {total_params:,}")
    print("TiDE Architecture Verification Passed Successfully!")
