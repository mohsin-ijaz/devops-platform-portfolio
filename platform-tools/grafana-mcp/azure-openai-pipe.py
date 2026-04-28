import requests
import json
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        AZURE_OPENAI_API_KEY: str = Field(
            default="<AZURE_AI_API_KEY>",
            description="Azure OpenAI API Key",
        )
        AZURE_OPENAI_ENDPOINT: str = Field(
            default="https://<YOUR_AZURE_ENDPOINT>.cognitiveservices.azure.com",
            description="Azure OpenAI Endpoint (base URL)",
        )
        AZURE_OPENAI_DEPLOYMENT: str = Field(
            default="gpt-5.2",
            description="Azure OpenAI Deployment Name",
        )
        AZURE_OPENAI_API_VERSION: str = Field(
            default="2024-12-01-preview",
            description="Azure OpenAI API Version",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "azure-openai"
        self.name = "azure-openai/"
        self.valves = self.Valves()

    def get_azure_models(self):
        return [
            {"id": "gpt-5.2", "name": "GPT-5.2 (Azure)"},
        ]

    def pipes(self) -> List[dict]:
        return self.get_azure_models()

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        # Construct the Azure OpenAI URL
        url = f"{self.valves.AZURE_OPENAI_ENDPOINT}/openai/deployments/{self.valves.AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={self.valves.AZURE_OPENAI_API_VERSION}"

        headers = {
            "Content-Type": "application/json",
            "api-key": self.valves.AZURE_OPENAI_API_KEY,
        }

        try:
            # Extract messages
            messages = body.get("messages", [])

            # Build payload - use max_completion_tokens for newer models
            payload = {
                "messages": messages,
                "max_completion_tokens": body.get("max_tokens", 4096),
            }

            # Add optional parameters if present
            if "temperature" in body:
                payload["temperature"] = body["temperature"]
            if "top_p" in body:
                payload["top_p"] = body["top_p"]

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,
            )

            if response.status_code == 200:
                res = response.json()
                choices = res.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    return message.get("content", "")
                return ""
            else:
                return f"Error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"Error: {str(e)}"
