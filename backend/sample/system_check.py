import torch
import platform


class DeviceManager:
    def __init__(self):

        self.info = self.get_device()
        self.device_type = self.info["type"]
        self.device = self.info["device"]

    def get_device(self):
        if torch.cuda.is_available():
            return {
                "type": "nvidia",
                "name": torch.cuda.get_device_name(0),
                "memory_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
                "device": "cuda"
            }

        elif torch.backends.mps.is_available():
            return {
                "type": "apple_silicon",
                "name": platform.processor(),
                "device": "mps"
            }
        else:
            return {
                "type": "cpu",
                "name": platform.processor(),
                "device": "cpu"
            }

    def to_device(self, tensor):
        return tensor.to(self.device)

    def is_nvidia(self):
        return self.device_type == "nvidia"

    def is_apple_silicon(self):
        return self.device_type == "apple_silicon"

    def summary(self):
        print(f"Device type:  {self.info['type']}")
        print(f"Device name:  {self.info['name']}")
        print(f"Torch device: {self.info['device']}")
        if self.is_nvidia():
            print(f"VRAM:         {self.info['memory_gb']} GB")
            


if __name__ == "__main__":
    
    device_manager = DeviceManager()
    device_manager.summary()