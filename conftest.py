import pytest


@pytest.fixture(autouse=True)
def no_real_ai(settings):
    """Tests never call a real AI provider; tests that need one patch the client."""
    settings.GROQ_API_KEY = ""
    settings.OPENAI_API_KEY = ""
    settings.AI_PROVIDER = "auto"
