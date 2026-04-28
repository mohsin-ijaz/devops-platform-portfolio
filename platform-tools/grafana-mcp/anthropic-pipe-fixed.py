import os
import requests
import json
import re
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        ANTHROPIC_API_KEY: str = Field(
            default="<AZURE_AI_API_KEY>",
            description="Azure AI Foundry API Key",
        )
        ANTHROPIC_API_URL: str = Field(
            default="https://<YOUR_AZURE_ENDPOINT>.ai.azure.com/anthropic/v1/messages",
            description="API Endpoint URL",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "anthropic"
        self.name = "anthropic/"
        self.valves = self.Valves()

    def get_anthropic_models(self):
        return [
            {"id": "claude-sonnet-4-6", "name": "claude-sonnet-4.6"},
        ]

    def pipes(self) -> List[dict]:
        return self.get_anthropic_models()

    def convert_content_to_anthropic_format(self, content):
        """Convert OpenAI format content to Anthropic format"""
        # If content is just a string, return as-is
        if isinstance(content, str):
            return content

        # If content is a list (multimodal content)
        if isinstance(content, list):
            converted_content = []
            for item in content:
                if isinstance(item, dict):
                    # Handle text content
                    if item.get("type") == "text":
                        converted_content.append({
                            "type": "text",
                            "text": item.get("text", "")
                        })
                    # Handle image_url (OpenAI format) -> image (Anthropic format)
                    elif item.get("type") == "image_url":
                        image_url = item.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else image_url

                        # Handle base64 encoded images
                        if url.startswith("data:"):
                            # Extract media type and base64 data
                            # Format: data:image/png;base64,iVBORw0KG...
                            match = re.match(r'data:([^;]+);base64,(.+)', url)
                            if match:
                                media_type = match.group(1)
                                base64_data = match.group(2)
                                converted_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_data
                                    }
                                })
                        else:
                            # Handle URL images (if supported)
                            converted_content.append({
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": url
                                }
                            })
                    # Pass through other Anthropic-native types
                    elif item.get("type") in ["image", "tool_use", "tool_result"]:
                        converted_content.append(item)
                    else:
                        # For unknown types, try to preserve as-is or convert to text
                        if "text" in item:
                            converted_content.append({
                                "type": "text",
                                "text": str(item.get("text", ""))
                            })

            return converted_content if converted_content else content

        # Fallback: return as-is
        return content

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        headers = {
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": self.valves.ANTHROPIC_API_KEY,
        }

        try:
            # Extract messages
            messages = body.get("messages", [])

            # Separate system message and convert content format
            system_message = None
            processed_messages = []

            for msg in messages:
                if msg.get("role") == "system":
                    system_message = msg.get("content", "")
                else:
                    # Convert content from OpenAI format to Anthropic format
                    original_content = msg.get("content", "")
                    converted_content = self.convert_content_to_anthropic_format(original_content)

                    processed_messages.append({
                        "role": msg.get("role"),
                        "content": converted_content
                    })

            payload = {
                "model": body.get("model", "claude-sonnet-4-6").replace(
                    "anthropic.", ""
                ),
                "messages": processed_messages,
                "max_tokens": body.get("max_tokens", 4096),
            }

            if system_message:
                payload["system"] = system_message

            response = requests.post(
                self.valves.ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )

            if response.status_code == 200:
                res = response.json()
                for content in res.get("content", []):
                    if content.get("text"):
                        return content["text"]
                return ""
            else:
                return f"Error: {response.status_code} - {response.text}"

        except Exception as e:
            return f"Error: {str(e)}"
