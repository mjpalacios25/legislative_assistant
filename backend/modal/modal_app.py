import modal
from transformers import AutoTokenizer, AutoModelForCausalLM

# Create a Modal image using Debian slim and install required dependencies
image = modal.Image.debian_slim().pip_install("fastapi[standard]", "transformers")

# Initialize a Modal App with the custom image
app = modal.App(name="example-lifecycle-web", image=image)

# Define a stub class for your model - Modal doesn't provide a Model class for this purpose
class MyModel:  # Remove inheritance from modal.Model
    def __init__(self):
        # Load the tokenizer and model once during initialization
        self.tokenizer = AutoTokenizer.from_pretrained("facebook/opt-125m")
        self.model = AutoModelForCausalLM.from_pretrained("facebook/opt-125m", device_map="auto")

    def run_inference(self, input_text: str) -> str:
        # Perform inference and return the result
        input_ids = self.tokenizer(input_text, return_tensors="pt")
        outputs = self.model.generate(**input_ids)
        return self.tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

# Define the web endpoint to accept requests and run inference
@app.function()
@modal.web_endpoint()  # Expose this function via an HTTP endpoint
def hello(input_text: str) -> str:
    # Initialize the model here, it will persist between calls
    if not hasattr(hello, "model_instance"): # Only initialize on first call
        hello.model_instance = MyModel()
    result = hello.model_instance.run_inference(input_text)  # Run inference
    return result

# To run the web app
if __name__ == "__main__":
    app.run()