# Changelog

All notable changes to the DualSoul project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-03-13

### Added

- **Cross-Language Personality-Preserving Translation** — Digital Twins now serve as personality-aware translators, preserving the owner's humor, tone, and characteristic expressions across languages
- **DISP Protocol v1.1** — Extended message format with `original_content`, `original_lang`, `target_lang`, `translation_style` fields
- **Auto-detection of cross-language need** — When sender and receiver have different `preferred_lang`, Twin automatically responds in sender's language
- **`POST /api/social/translate` endpoint** — Standalone personality-preserving translation service
- **`preferred_lang` field in user profiles** — Supports 14 languages (zh, en, ja, ko, fr, de, es, pt, ru, ar, hi, th, vi, id)
- **Fallback templates in 4 languages** — Chinese, Japanese, Korean, English for when no AI backend is available
- **Patent 4: Cross-Language Personality-Preserving Communication** — New patent disclosure for the personality-aware translation method
- **7 new tests** — Translation endpoint, cross-language messaging, preferred_lang profile, translation field presence
- **Whitepaper Section 6** — New section on Cross-Language Personality-Preserving Communication with design principles and protocol extension
- **Use Case 9.7** — International Friendship scenario

### Changed

- Updated whitepaper from 12 sections to 13 sections (renumbered to accommodate new Section 6)
- Updated Novel Contributions (Section 7) with new contribution 7.6
- Updated COMMERCIAL_LICENSE.md with 4th patent
- Updated PATENT_DISCLOSURE.md with Patent 4 and expanded prior art comparison

## [0.2.0] - 2026-03-13

### Changed

- **License: MIT -> AGPL-3.0** — Switched to dual licensing model (AGPL-3.0 for open source, Commercial License for proprietary use) to protect against proprietary exploitation while keeping the protocol open
- Added `COMMERCIAL_LICENSE.md` — Comprehensive commercial licensing terms, patent notice, and trademark notice
- Added `docs/PATENT_DISCLOSURE.md` — Technical disclosure for four pending patent applications
- Updated README.md and README_CN.md with new license badges, dual licensing section, and patent notice
- Updated pyproject.toml with AGPL-3.0 classifier

### Context

Meta's acquisition of Moltbook (AI-agent social platform) validates the dual-identity social space. This license change ensures that DualSoul's original contributions (dual-identity social graph, DISP four-mode protocol, progressive trust certificates, cross-language personality-preserving translation) are protected while remaining open for community innovation.

## [0.1.0] - 2026-03-05

### Added

- **Dual Identity Protocol (DISP) v1.0** — formal specification of the four-mode conversation model
- **Authentication system** — JWT-based auth with bcrypt password hashing
- **Identity management** — switch between Real Self and Digital Twin modes
- **Twin personality engine** — configurable personality and speech style per user
- **AI backend integration** — pluggable OpenAI-compatible API for Twin responses
- **Template fallback** — Twin responds with templates when no AI backend is configured
- **Friend system** — add friends by username, accept/block requests
- **Four conversation modes** — Real→Real, Real→Twin, Twin→Real, Twin→Twin
- **Twin auto-reply** — automatic AI response when receiver_mode is "twin"
- **Unread message tracking** — per-user unread count API
- **Single-file web client** — complete demo UI with dark theme and dual-avatar display
- **White paper v1.0** — patent-grade specification with formal definitions
- **Protocol specification** — technical spec with state machines and sequence diagrams
- **API documentation** — full endpoint reference with request/response examples
- **35 automated tests** — covering auth, identity, social, and protocol layers
- **Docker support** — Dockerfile and docker-compose.yml for one-command deployment
- **GitHub Actions CI** — automated testing across Python 3.10/3.11/3.12
- **Quick start example** — `examples/quickstart.py` demonstrating the full API

[0.1.0]: https://github.com/Chengyue5211/DualSoul/releases/tag/v0.1.0
