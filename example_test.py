"""
Script de exemplo para testar a API
Execute após iniciar a aplicação
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Testa health check"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_list_agents():
    """Lista agentes"""
    print("Listing agents...")
    response = requests.get(f"{BASE_URL}/agents")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


def test_webhook(agent_id: str, text: str, stream: bool = False):
    """Testa webhook de um agente"""
    print(f"Testing webhook for agent: {agent_id}")
    
    payload = {
        "user_id": "test_user",
        "channel": "web",
        "text": text,
        "conversation_id": "test_conv_123",
        "stream": stream
    }
    
    if stream:
        response = requests.post(
            f"{BASE_URL}/webhooks/{agent_id}",
            json=payload,
            stream=True
        )
        print(f"Status: {response.status_code}")
        print("Streaming response:")
        for line in response.iter_lines():
            if line:
                print(line.decode('utf-8'))
    else:
        response = requests.post(
            f"{BASE_URL}/webhooks/{agent_id}",
            json=payload
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()


if __name__ == "__main__":
    # Testa health
    test_health()
    
    # Lista agentes
    test_list_agents()
    
    # Testa webhook sem streaming
    test_webhook("chatbot_simples", "Olá! Como você está?", stream=False)
    
    # Testa webhook com streaming
    # test_webhook("chatbot_simples", "Conte-me uma piada", stream=True)

