#!/usr/bin/env bash

set -Eeuo pipefail

readonly KEYCHAIN_SERVICE="fin-guardrail-api"
readonly KEYCHAIN_ACCOUNT="OLLAMA_API_KEY"
readonly REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

use_mock_llm=true
ollama_api_key=""

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker command not found" >&2
    exit 1
fi

if [[ "${1:-}" == "--live" ]]; then
    shift
    use_mock_llm=false

    if ! command -v security >/dev/null 2>&1; then
        echo "error: macOS security command not found" >&2
        exit 1
    fi

    if ! ollama_api_key="$(security find-generic-password \
        -s "${KEYCHAIN_SERVICE}" \
        -a "${KEYCHAIN_ACCOUNT}" \
        -w)"; then
        echo "error: could not read ${KEYCHAIN_ACCOUNT} from macOS Keychain" >&2
        exit 1
    fi

    if [[ -z "${ollama_api_key}" ]]; then
        echo "error: Keychain returned an empty ${KEYCHAIN_ACCOUNT}" >&2
        exit 1
    fi
fi

cd "${REPO_DIR}"
USE_MOCK_LLM="${use_mock_llm}" \
OLLAMA_API_KEY="${ollama_api_key}" \
exec docker compose up -d "$@"
