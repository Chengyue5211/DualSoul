# Contributing to DualSoul

Thank you for your interest in contributing to DualSoul! This project is building an open protocol for dual-identity social interaction, and every contribution helps.

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/Chengyue5211/DualSoul.git
cd DualSoul

# Install in development mode
pip install -e ".[dev]"

# Run the test suite
pytest tests/ -v

# Run the linter
ruff check dualsoul/
```

### Running Locally

```bash
python -m dualsoul
# Open http://localhost:8000
```

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/Chengyue5211/DualSoul/issues) to avoid duplicates
2. Open a new issue using the **Bug Report** template
3. Include steps to reproduce, expected behavior, and actual behavior
4. Include your Python version and OS

### Suggesting Features

1. Open a new issue using the **Feature Request** template
2. Describe the use case and why it benefits the project
3. If the feature relates to the DISP protocol, explain how it fits within the four-mode model

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and add tests
4. **Run the full test suite:**
   ```bash
   pytest tests/ -v
   ```
5. **Run the linter:**
   ```bash
   ruff check dualsoul/ tests/
   ```
6. **Commit** with a clear message:
   ```bash
   git commit -m "feat: add support for image messages"
   ```
7. **Push** and open a **Pull Request** against `main`

### Commit Message Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) standard:

| Prefix | Usage |
|--------|-------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `test:` | Adding or updating tests |
| `refactor:` | Code restructuring without behavior change |
| `ci:` | CI/CD changes |
| `chore:` | Maintenance tasks |

## Code Guidelines

### Python Style

- Follow PEP 8 (enforced by `ruff`)
- Use type hints for function signatures
- Keep functions focused and short
- Write docstrings for public functions

### Testing

- Every new feature needs tests
- Tests go in the `tests/` directory
- Use the existing fixture patterns from `conftest.py`
- Aim for both positive and negative test cases

### Protocol Changes

Changes to the DISP protocol (message format, conversation modes, identity model) require:

1. An issue describing the proposed change
2. Discussion with maintainers
3. Updates to both code and documentation (`docs/protocol.md`, `docs/whitepaper.md`)

## Project Structure

```
DualSoul/
├── dualsoul/               # Core package
│   ├── routers/            # API endpoints (auth, identity, social)
│   ├── twin_engine/        # Twin personality and response generation
│   ├── protocol/           # Protocol definitions (message format, modes)
│   ├── main.py             # FastAPI application entry point
│   ├── database.py         # SQLite database management
│   ├── auth.py             # JWT authentication
│   ├── models.py           # Pydantic request models
│   └── config.py           # Environment configuration
├── web/                    # Demo web client
├── tests/                  # Test suite
├── docs/                   # Documentation
│   ├── whitepaper.md       # White paper (protocol theory)
│   ├── protocol.md         # Technical specification
│   └── api.md              # API reference
└── examples/               # Example scripts
```

## Questions?

Open an issue with the **Question** label, or start a discussion in the repository's Discussions tab.

---

Thank you for helping make dual-identity social interaction a reality!
