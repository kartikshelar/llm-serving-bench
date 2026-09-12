#!/bin/bash
set -euo pipefail
exec > >(tee /home/ubuntu/setup.log) 2>&1
echo "SETUP_START $(date -Is)"
export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -y
sudo apt-get install -y build-essential curl ca-certificates gnupg lsb-release ubuntu-drivers-common

echo "INSTALL_NVIDIA $(date -Is)"
sudo ubuntu-drivers install -y || sudo apt-get install -y nvidia-driver-550

echo "INSTALL_DOCKER $(date -Is)"
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

echo "INSTALL_NVIDIA_CTK $(date -Is)"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update -y
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "SETUP_PRE_REBOOT $(date -Is)"
sudo reboot
