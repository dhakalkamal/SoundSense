"""Minimal CNN14 model architecture matching the PANNs checkpoint."""

import torch
import torch.nn as nn
import torch.nn.functional as F


def init_layer(layer: nn.Module) -> None:
    """Xavier-uniform weight init; zero bias."""
    nn.init.xavier_uniform_(layer.weight)
    if layer.bias is not None:
        layer.bias.data.fill_(0.0)


def init_bn(bn: nn.Module) -> None:
    """Standard BatchNorm init: weight=1, bias=0."""
    bn.weight.data.fill_(1.0)
    bn.bias.data.fill_(0.0)


class ConvBlock(nn.Module):
    """Two-layer conv block with BN, ReLU, and configurable pooling."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.bn2 = nn.BatchNorm2d(out_channels)
        init_layer(self.conv1)
        init_layer(self.conv2)
        init_bn(self.bn1)
        init_bn(self.bn2)

    def forward(self, x: torch.Tensor, pool_size=(2, 2), pool_type: str = "avg") -> torch.Tensor:
        x = F.relu_(self.bn1(self.conv1(x)))
        x = F.relu_(self.bn2(self.conv2(x)))
        if pool_type == "max":
            x = F.max_pool2d(x, pool_size)
        elif pool_type == "avg":
            x = F.avg_pool2d(x, pool_size)
        elif pool_type == "avg+max":
            x = F.avg_pool2d(x, pool_size) + F.max_pool2d(x, pool_size)
        return x


class Cnn14(nn.Module):
    """CNN14 model from PANNs — outputs 527-class AudioSet sigmoid probabilities."""

    def __init__(self, classes_num: int = 527) -> None:
        super().__init__()
        self.bn0 = nn.BatchNorm2d(64)
        self.conv_block1 = ConvBlock(1, 64)
        self.conv_block2 = ConvBlock(64, 128)
        self.conv_block3 = ConvBlock(128, 256)
        self.conv_block4 = ConvBlock(256, 512)
        self.conv_block5 = ConvBlock(512, 1024)
        self.conv_block6 = ConvBlock(1024, 2048)
        self.fc1 = nn.Linear(2048, 2048, bias=True)
        self.fc_audioset = nn.Linear(2048, classes_num, bias=True)
        init_bn(self.bn0)
        init_layer(self.fc1)
        init_layer(self.fc_audioset)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, time_steps, mel_bins)
        x = x.unsqueeze(1)
        x = x.transpose(1, 3)
        x = self.bn0(x)
        x = x.transpose(1, 3)
        x = self.conv_block1(x, pool_size=(2, 2), pool_type="avg+max")
        x = F.dropout(x, p=0.2, training=self.training)
        x = self.conv_block2(x, pool_size=(2, 2), pool_type="avg+max")
        x = F.dropout(x, p=0.2, training=self.training)
        x = self.conv_block3(x, pool_size=(2, 2), pool_type="avg+max")
        x = F.dropout(x, p=0.2, training=self.training)
        x = self.conv_block4(x, pool_size=(2, 2), pool_type="avg+max")
        x = F.dropout(x, p=0.2, training=self.training)
        x = self.conv_block5(x, pool_size=(2, 2), pool_type="avg+max")
        x = F.dropout(x, p=0.2, training=self.training)
        x = self.conv_block6(x, pool_size=(1, 1), pool_type="avg+max")
        x = F.dropout(x, p=0.2, training=self.training)
        x = torch.mean(x, dim=3)
        x1, _ = torch.max(x, dim=2)
        x2 = torch.mean(x, dim=2)
        x = x1 + x2
        x = F.dropout(x, p=0.5, training=self.training)
        x = F.relu_(self.fc1(x))
        return torch.sigmoid(self.fc_audioset(x))
