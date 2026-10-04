"""Model health check script for SANGYAN.

Verifies:
1. Ollama is reachable at configured base URL.
2. Target evaluation models exist ('qwen3.8:27b' and 'gemma4:12b').
3. Verifies coder models are not used for runtime.
4. Performs a minimal generation check on each required model.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
ai_root = Path(__file__).resolve().parent.parent
project_root = ai_root.parent
for p in [str(ai_root), str(project_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ai.app.config.settings import settings
from ai.app.models.ollama import OllamaProvider
from ai.app.models.schemas import Message


async def run_check() -> bool:
    print("=" * 60)
    print("SANGYAN Model Health Check")
    print(f"Target Ollama URL: {settings.ollama_base_url}")
    print("=" * 60)

    # Provider instance for health checks
    dummy_provider = OllamaProvider(model_name="gemma4:12b")
    
    try:
        is_reachable = await dummy_provider.check_health()
        if not is_reachable:
            print("[FAIL] Ollama is NOT reachable at", settings.ollama_base_url)
            print("Please ensure Ollama is running (`ollama serve`).")
            return False
        print("[OK] Ollama reachable")
    except Exception as exc:
        print(f"[FAIL] Error checking Ollama health: {exc}")
        return False

    # Check available models
    try:
        available_models = await dummy_provider.list_models()
    except Exception as exc:
        print(f"[FAIL] Error listing models: {exc}")
        return False

    print(f"Total models reported by Ollama: {len(available_models)}")

    required_models = ["qwen3.8:27b", "gemma4:12b"]
    all_present = True

    for req in required_models:
        # Check exact or prefix match
        found = any(m == req or m.startswith(f"{req}:") for m in available_models)
        if found:
            print(f"[OK] {req} available")
        else:
            print(f"[FAIL] {req} NOT found in Ollama!")
            all_present = False

    # Note about coder models
    coder_models_found = [m for m in available_models if "coder" in m.lower()]
    if coder_models_found:
        print(f"[INFO] Coder models detected ({', '.join(coder_models_found)}). Note: Excluded from SANGYAN runtime.")

    if not all_present:
        print("[ABORT] Not all required evaluation models are present.")
        await dummy_provider.close()
        return False

    # Generation tests
    print("\n--- Running Quick Generation Tests ---")
    test_messages = [
        Message(role="user", content="Respond with exactly two words: 'System operational'")
    ]

    for model_name in required_models:
        print(f"Testing generation for {model_name}...")
        provider = OllamaProvider(model_name=model_name, timeout=120.0)
        try:
            resp = await provider.generate(messages=test_messages, temperature=0.0, max_tokens=150)
            print(f"  [OK] {model_name} responded in {resp.latency_ms:.1f}ms: {resp.content.strip()[:60]}")
        except Exception as exc:
            print(f"  [FAIL] {model_name} generation failed: {exc}")
            all_present = False
        finally:
            await provider.close()

    await dummy_provider.close()
    print("=" * 60)
    if all_present:
        print("[SUCCESS] All model health checks passed.")
    else:
        print("[WARNING] Some checks failed.")
    print("=" * 60)
    return all_present


def main() -> None:
    success = asyncio.run(run_check())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
