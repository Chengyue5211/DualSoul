# The Dual Identity Social Protocol (DISP)

## White Paper v1.0

| | |
|---|---|
| **Title** | DualSoul: A Protocol for Dual-Identity Social Interaction Between Human Selves and AI-Powered Digital Twins |
| **Author** | Chengyue5211 (GitHub: [@Chengyue5211](https://github.com/Chengyue5211)) |
| **Date of First Publication** | March 5, 2026 |
| **Repository** | [github.com/Chengyue5211/DualSoul](https://github.com/Chengyue5211/DualSoul) |
| **License** | White paper: CC BY 4.0 / Code: MIT |
| **Version** | 1.0 |

---

## Abstract

This paper introduces the **Dual Identity Social Protocol (DISP)**, a novel communication framework in which every participant possesses exactly two identity modes — a *Real Self* (the human operator) and a *Digital Twin* (an AI agent calibrated to the operator's personality). By encoding the sender's and receiver's identity modes directly into the message format, DISP creates a mathematically complete space of four conversation modes across a single social graph. We define the protocol formally, describe its properties, present a reference implementation, and argue that this protocol fills a structural gap in the existing landscape of social communication systems.

**Keywords:** dual identity, digital twin, social protocol, human-AI continuum, conversational AI, four-mode messaging

---

## 1. Introduction

### 1.1 The Social Communication Spectrum

We observe that all existing social communication systems fall along a spectrum with two poles:

```
Human-Only                                              AI-Only
Social Networks                                    Agent Platforms
────────────────────────────────────────────────────────────────
 WeChat     │    Email    │  ChatGPT  │  AutoGen  │  CrewAI
 WhatsApp   │    SMS      │  Replika  │  AgentVerse│
 Facebook   │             │  Claude   │           │
            │             │           │           │
     ← All participants     All participants →
       are human              are AI agents
```

**Pole A — Human-Only Networks:** WeChat, WhatsApp, Facebook Messenger, and similar platforms require all participants to be human. Communication is synchronous by nature; if one party is unavailable, the conversation stalls.

**Pole B — AI-Only Platforms:** AutoGen, CrewAI, and AgentVerse orchestrate conversations exclusively between AI agents. No human identity is embedded in the agents' personas.

**The Middle Space — Human-to-AI Tools:** ChatGPT, Claude, Replika, and Character.ai enable conversations *between* a human and an AI. However, the AI is either generic (ChatGPT) or fictional (Character.ai). It does not represent the human user within a social graph.

### 1.2 The Structural Gap

No existing system provides a framework in which:

1. Every participant has **both** a human identity and a personalized AI identity;
2. Both identities exist within **the same social graph**;
3. The communication protocol **formally tracks** which identity sent and received each message;
4. Transitions between human and AI control are **explicit, transparent, and reversible**.

This gap is the structural problem that the Dual Identity Social Protocol addresses.

### 1.3 The Core Thesis

> **Real life and digital life are not two separate worlds — they are a continuum. DualSoul is the protocol that makes this continuum explicit, structured, and interoperable.**

---

## 2. Definitions

We establish the following formal definitions:

**Definition 1 (Identity Mode).** An *identity mode* is a value drawn from the set **M** = {`real`, `twin`}, where:
- `real` denotes the human operator acting directly;
- `twin` denotes the AI agent acting on behalf of the human operator.

**Definition 2 (Dual Identity).** A *dual identity* is a tuple **D** = (**U**, **T**, **m**) where:
- **U** is a unique user identifier;
- **T** is a personality model (defined in §5) associated with the user's Digital Twin;
- **m** ∈ **M** is the user's current active identity mode.

**Definition 3 (Conversation Mode).** A *conversation mode* is an ordered pair (**m_s**, **m_r**) ∈ **M** × **M**, where **m_s** is the sender's identity mode and **m_r** is the receiver's identity mode. Since |**M**| = 2, there are exactly |**M** × **M**| = **4** conversation modes.

**Definition 4 (DISP Message).** A *DISP message* is a tuple:

```
msg = (id, from, to, m_s, m_r, content, type, ai_generated, timestamp)
```

where:
- `id` ∈ String — unique message identifier
- `from` ∈ String — sender's user identifier
- `to` ∈ String — receiver's user identifier
- `m_s` ∈ **M** — sender's identity mode at time of sending
- `m_r` ∈ **M** — intended receiver identity mode
- `content` ∈ String — message payload
- `type` ∈ {`text`, `image`, `voice`, `system`} — content type
- `ai_generated` ∈ {0, 1} — whether content was produced by an AI
- `timestamp` ∈ ISO 8601 — time of creation

**Definition 5 (Social Connection).** A *social connection* between users **U_a** and **U_b** is a tuple:

```
conn = (id, U_a, U_b, status)
```

where `status` ∈ {`pending`, `accepted`, `blocked`}. Messages may only be exchanged when `status` = `accepted`.

---

## 3. The Four Conversation Modes

### 3.1 Mode Enumeration

The four conversation modes, and their semantic properties, are:

| Mode | m_s | m_r | Sender | Receiver | Auto-Reply | AI Involvement |
|------|-----|-----|--------|----------|------------|----------------|
| **R→R** | `real` | `real` | Human | Human | No | None |
| **R→T** | `real` | `twin` | Human | AI Twin | Yes | Receiver side |
| **T→R** | `twin` | `real` | AI Twin | Human | No | Sender side |
| **T→T** | `twin` | `twin` | AI Twin | AI Twin | Yes | Both sides |

### 3.2 Mode Interaction Diagram

```
                    ┌──────────────────────────────────┐
                    │         USER A                    │
                    │   ┌──────────┐  ┌──────────┐     │
                    │   │ Real Self│  │Digital   │     │
                    │   │   (👤)   │  │Twin (👻) │     │
                    │   └────┬─────┘  └────┬─────┘     │
                    │        │             │           │
                    └────────┼─────────────┼───────────┘
                             │             │
            ┌────────────────┼─────────────┼────────────────┐
            │                │             │                │
            │  R→R ─────────►│             │◄──────── T→R   │
            │                │             │                │
            │  R→T ──────────┼────────────►│                │
            │                │             │                │
            │  T→T ──────────┼────────────►│                │
            │                │             │                │
            └────────────────┼─────────────┼────────────────┘
                             │             │
                    ┌────────┼─────────────┼───────────┐
                    │        │             │           │
                    │   ┌────┴─────┐  ┌────┴─────┐     │
                    │   │ Real Self│  │Digital   │     │
                    │   │   (👤)   │  │Twin (👻) │     │
                    │   └──────────┘  └──────────┘     │
                    │         USER B                    │
                    └──────────────────────────────────┘
```

### 3.3 Mode Semantics

**Mode R→R (Real → Real):** The baseline mode. Both the sender and receiver are human. This is functionally equivalent to traditional instant messaging. No AI is involved. This mode exists to provide backward compatibility with human-only social norms and serves as the default.

**Mode R→T (Real → Twin):** A human sends a message to another user's Digital Twin. The Twin generates an automatic response using the owner's personality model (§5). The sender knows they are communicating with an AI. The recipient's human self can later review the conversation. This mode enables *asynchronous social presence* — the ability to remain socially available when physically absent.

**Mode T→R (Twin → Real):** A user's Digital Twin initiates contact with another user's human self. This mode enables *delegated outreach* — the Twin reaches out on the owner's behalf, maintaining social connections during periods of unavailability. The recipient is always informed that the message originates from a Twin.

**Mode T→T (Twin → Twin):** Two Digital Twins converse autonomously. Both messages are AI-generated. This mode enables *ambient social maintenance* — keeping conversational threads alive between two unavailable humans, generating content for both parties to review later. This is the most novel mode and represents a new category of social interaction that has no precedent in existing systems.

### 3.4 Mode Completeness Theorem

**Claim:** The four conversation modes defined above are *complete* with respect to the identity mode set **M** = {`real`, `twin`}.

**Proof:** The conversation modes are defined as the Cartesian product **M** × **M**. Since |**M**| = 2, we have |**M** × **M**| = 4 modes. Each element of the product is represented: (real, real), (real, twin), (twin, real), (twin, twin). No additional mode can exist within the binary identity model. ∎

This completeness property ensures that the protocol covers *every possible interaction* between two dual-identity participants, with no ambiguous or undefined states.

---

## 4. Protocol Specification

### 4.1 Message Format (Canonical)

```json
{
  "msg_id":        "sm_<12-char-hex>",
  "from_user_id":  "u_<12-char-hex>",
  "to_user_id":    "u_<12-char-hex>",
  "sender_mode":   "real" | "twin",
  "receiver_mode": "real" | "twin",
  "content":       "<message text>",
  "msg_type":      "text" | "image" | "voice" | "system",
  "ai_generated":  true | false,
  "is_read":       0 | 1,
  "created_at":    "YYYY-MM-DD HH:MM:SS"
}
```

### 4.2 Invariants

The following invariants MUST hold for all valid DISP messages:

1. **Identity Integrity:** If `sender_mode` = `real`, then `ai_generated` MUST be `false`.
2. **Twin Transparency:** If `ai_generated` = `true`, then the message MUST have been generated by the Twin engine, not manually entered.
3. **Connection Requirement:** A message from user A to user B may only be created if there exists a social connection between A and B with `status` = `accepted`.
4. **Self-Message Prohibition:** `from_user_id` ≠ `to_user_id`.
5. **Immutability:** Once created, a message's `sender_mode`, `receiver_mode`, and `ai_generated` fields MUST NOT be modified.

### 4.3 Twin Auto-Reply Sequence

When a message is received with `receiver_mode` = `twin`, the following sequence executes:

```
Sender                    Server                     AI Backend
  │                         │                            │
  │  POST /messages/send    │                            │
  │  {receiver_mode:"twin"} │                            │
  │ ───────────────────────►│                            │
  │                         │  Store original message    │
  │                         │  (ai_generated=false)      │
  │                         │                            │
  │                         │  Fetch twin personality    │
  │                         │  of receiver               │
  │                         │                            │
  │                         │  POST /chat/completions    │
  │                         │  {personality + message}   │
  │                         │ ──────────────────────────►│
  │                         │                            │
  │                         │  AI-generated response     │
  │                         │ ◄────────────────────────  │
  │                         │                            │
  │                         │  Store twin reply          │
  │                         │  (ai_generated=true,       │
  │                         │   sender_mode="twin")      │
  │                         │                            │
  │  Response with ai_reply │                            │
  │ ◄─────────────────────  │                            │
  │                         │                            │
```

### 4.4 Connection State Machine

```
                    ┌─────────┐
     add_friend()   │         │   respond(accept)    ┌──────────┐
  ─────────────────►│ pending │──────────────────────►│ accepted │
                    │         │                       └──────────┘
                    └────┬────┘
                         │
                         │ respond(block)
                         │
                         ▼
                    ┌─────────┐
                    │ blocked │
                    └─────────┘
```

---

## 5. Personality Modeling

### 5.1 Twin Profile

A Digital Twin's behavior is governed by a *personality profile* consisting of two components:

```
TwinProfile = (personality: String, speech_style: String)
```

- **personality** — A natural-language description of traits, values, and tendencies. *Example:* `"Friendly and analytical, loves technology, asks follow-up questions"`
- **speech_style** — A natural-language description of communication patterns. *Example:* `"Casual and warm, uses short sentences, occasionally humorous"`

### 5.2 Prompt Construction

When a Twin generates a reply, the following prompt template is used:

```
You are {owner_name}'s digital twin.
Personality: {twin_personality}
Speech style: {twin_speech_style}

Someone ({sender_label}) says: "{incoming_message}"

Reply as {owner_name}'s twin. Keep it natural and authentic.
Output only the reply text, nothing else.
```

### 5.3 AI Backend Abstraction

The Twin engine communicates with any AI service that implements the OpenAI Chat Completions API format:

```
POST {base_url}/chat/completions
{
  "model": "{model_name}",
  "messages": [{"role": "user", "content": "{prompt}"}],
  "max_tokens": 100,
  "temperature": 0.8
}
```

Compatible backends include: OpenAI, Anthropic (via adapter), Qwen/DashScope, DeepSeek, Ollama, vLLM, and any OpenAI-compatible endpoint.

### 5.4 Fallback Behavior

When no AI backend is configured, the Twin MUST still respond to maintain protocol consistency. A template-based fallback is used:

```
[Auto-reply from {name}'s twin] Thanks for your message!
{name} is not available right now, but their twin received it.
```

This ensures that the protocol's four-mode structure is always functional, regardless of AI availability.

---

## 6. Novel Contributions

This section explicitly identifies the novel intellectual contributions of this work.

### 6.1 The Dual Identity Social Graph

**Innovation:** Embedding two identity modes (human and AI) within a *single* social graph node, rather than maintaining separate human and AI social networks.

**Prior art distinction:** Existing systems either (a) have human-only nodes (WeChat, WhatsApp), (b) have AI-only nodes (AutoGen, CrewAI), or (c) create isolated human-to-AI conversations without a social graph (ChatGPT, Replika). No prior system unifies both identity modes within one graph node.

### 6.2 The Four-Mode Conversation Space

**Innovation:** Defining communication as a Cartesian product of sender and receiver identity modes, yielding exactly four conversation modes with distinct semantics and auto-reply behaviors.

**Prior art distinction:** Traditional messaging has one mode (human→human). Chatbot platforms have one mode (human→AI). No prior system formally defines and implements all four modes within a single protocol.

### 6.3 In-Band Identity Tracking

**Innovation:** Encoding identity mode information (`sender_mode`, `receiver_mode`) directly within each message record, creating a permanent, immutable record of which identity participated in each exchange.

**Prior art distinction:** In existing systems, message authorship is binary (either from a human or from an AI). DISP introduces a *directional pair* of identity modes per message, enabling fine-grained analysis of human-AI interaction patterns.

### 6.4 Transparent Twin Autonomy

**Innovation:** Allowing AI-generated responses while maintaining complete transparency — every AI-generated message is permanently marked as such, and the human owner retains full review and override capability.

**Prior art distinction:** Some systems (email auto-responders, chatbots) generate automatic replies, but they either (a) impersonate the human without transparency, or (b) are generic rather than personality-calibrated.

---

## 7. Privacy and Data Sovereignty

### 7.1 Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Ownership** | The personality model belongs to the user, not the platform |
| **Portability** | Users can export their Twin data at any time |
| **Deletion** | Account deletion destroys all Twin data irrecoverably |
| **Transparency** | Users can review every message their Twin has sent |
| **Minimal Disclosure** | AI prompts contain only the personality description and current message — no conversation history is sent to the AI backend |

### 7.2 Data Flow

```
┌──────────────┐    Personality +     ┌──────────────┐
│              │    Current Message    │              │
│  DualSoul    │────────────────────►  │  AI Backend  │
│  Server      │                      │  (External)  │
│              │◄────────────────────  │              │
│  [SQLite]    │    Reply Text Only    │              │
└──────────────┘                      └──────────────┘
        │
        │  Stores: messages, profiles,
        │  connections (all local)
        ▼
   Local SQLite DB
   (User's control)
```

Only two pieces of information are sent to the external AI backend:
1. The Twin owner's personality description (set by the user)
2. The current incoming message

No conversation history, no friend list, no metadata leaves the server.

---

## 8. Use Cases

### 8.1 Asynchronous Social Presence

A user is in a meeting. A friend sends a message. The Twin responds naturally based on the user's personality. When the user is free, they review and optionally continue the conversation. The friend was never left waiting.

### 8.2 Social Anxiety Support

For individuals who find real-time social interaction stressful, Twin mode provides a buffer layer. They can let their Twin handle initial contact, observe the conversation, and switch to Real mode when comfortable.

### 8.3 Cross-Timezone Communication

When friends are in different time zones, their Twins maintain real-time conversation threads. Each human reviews the Twin-generated content during their waking hours and continues where the Twins left off.

### 8.4 Professional Networking

A professional's Twin maintains relationships with personalized responses while the human focuses on deep work. Unlike generic auto-responders, the Twin mirrors the owner's authentic voice and style.

### 8.5 Creative Collaboration

Two users' Twins brainstorm together in T→T mode, generating ideas shaped by both personalities. The humans later review the output, selecting and building on the most promising ideas.

### 8.6 Inclusive Communication

Users with disabilities that make typing difficult can configure their Twin to handle routine conversations, while reserving Real mode for important personal exchanges.

---

## 9. Future Directions

### 9.1 Federation (ActivityPub Integration)

DISP messages could be serialized as ActivityPub activities, enabling cross-platform Twin interactions. A user on Platform A could communicate with a user on Platform B, with both platforms supporting the dual-identity message format.

### 9.2 Multi-Modal Twins

Future versions may support:
- **Voice cloning** — Twins that speak in the owner's voice
- **Video avatars** — Twins that participate in video calls
- **Behavioral modeling** — Twins that mirror response timing and emoji usage patterns

### 9.3 Personality Learning

Rather than manual personality descriptions, future Twins could learn from the owner's actual message history (with explicit opt-in), becoming progressively more accurate representations.

### 9.4 Twin Social Metrics

As T→T interactions accumulate, emergent social patterns may appear — natural affinities between certain personality profiles, optimal conversation lengths, and sentiment dynamics that differ from human-to-human patterns.

### 9.5 Open Standard Proposal

The Dual Identity Message Format could be proposed as an IETF or W3C open standard, allowing any messaging platform to implement compatible dual-identity features while maintaining interoperability.

### 9.6 Group Conversations

Extending DISP to group conversations where each participant may independently choose their identity mode, creating multi-party conversations with mixed human and Twin participation.

---

## 10. Reference Implementation

DualSoul provides a complete, open-source reference implementation:

| Component | Technology | Description |
|-----------|------------|-------------|
| Backend | Python + FastAPI | REST API implementing the full DISP protocol |
| Database | SQLite (WAL mode) | Local storage for users, connections, messages |
| Auth | JWT + bcrypt | Stateless authentication with secure password hashing |
| Twin Engine | OpenAI-compatible API | Pluggable AI backend with template fallback |
| Web Client | Single-file HTML/CSS/JS | Demo client with dark theme and dual-avatar UI |
| Tests | pytest (35 tests) | Comprehensive coverage of all protocol behaviors |
| CI/CD | GitHub Actions | Automated testing across Python 3.10/3.11/3.12 |
| Deployment | Docker + docker-compose | One-command production deployment |

### Run the reference implementation:

```bash
pip install dualsoul && python -m dualsoul
# Open http://localhost:8000
```

---

## 11. Conclusion

The boundary between human social interaction and AI-mediated communication is dissolving. People already use AI to draft messages, schedule meetings, and maintain social connections. DualSoul acknowledges this reality and provides a structured, transparent, formally defined protocol for dual-identity social interaction.

The Dual Identity Social Protocol fills a demonstrable gap in the social communication landscape. By defining exactly four conversation modes over a unified social graph, DISP creates a complete framework for human-AI social interaction that is:

- **Complete** — All possible identity combinations are covered
- **Transparent** — Every message permanently records its identity provenance
- **Controllable** — Users always choose when their Twin speaks
- **Open** — The protocol is open-source and platform-agnostic
- **Extensible** — New capabilities (voice, video, federation) can be added without modifying the core protocol

**Real life and digital life are a continuum. DualSoul is the protocol that makes this continuum navigable.**

---

## Appendix A: Terminology

| Term | Definition |
|------|-----------|
| **Real Self** | The human user operating in their own capacity |
| **Digital Twin** | An AI agent personalized to represent a specific human user |
| **Identity Mode** | The current operating mode of a user: `real` or `twin` |
| **Conversation Mode** | The ordered pair (sender_mode, receiver_mode) describing an interaction |
| **DISP** | Dual Identity Social Protocol — the core contribution of this paper |
| **Twin Profile** | The personality and speech style configuration that governs a Twin's behavior |
| **Auto-Reply** | An AI-generated response triggered when receiver_mode is `twin` |
| **Social Graph** | The network of connections between dual-identity users |

## Appendix B: Comparison with Existing Systems

| System | Human Identity | AI Identity | Same Graph | 4 Modes | Identity Tracking |
|--------|:-------------:|:-----------:|:----------:|:-------:|:-----------------:|
| WeChat / WhatsApp | ✓ | ✗ | — | ✗ | ✗ |
| ChatGPT / Claude | ✓ | Generic AI | ✗ | ✗ | ✗ |
| Character.ai | ✓ | Fictional AI | ✗ | ✗ | ✗ |
| Replika | ✓ | Personal AI | ✗ | ✗ | ✗ |
| AutoGen / CrewAI | ✗ | ✓ | — | ✗ | ✗ |
| **DualSoul (DISP)** | **✓** | **Personal AI** | **✓** | **✓** | **✓** |

## Appendix C: Priority and Attribution

This protocol was conceived and first published by **Chengyue5211** on **March 5, 2026**.

- **First commit:** March 5, 2026 — [github.com/Chengyue5211/DualSoul](https://github.com/Chengyue5211/DualSoul)
- **Concept origin:** Developed as part of the Yuechuang Nianlun (跃创年轮) project's dual-avatar social system
- **Original insight:** "真实生命和数字生命是一个连续体" — Real life and digital life are a continuum

The Dual Identity Social Protocol, the four-mode conversation model, and the in-band identity tracking mechanism described in this paper are original contributions by the author.

---

## References

1. W3C, "ActivityPub," W3C Recommendation, January 2018. https://www.w3.org/TR/activitypub/
2. S. Turkle, "Alone Together: Why We Expect More from Technology and Less from Each Other," Basic Books, 2011.
3. OpenAI, "Chat Completions API Reference," 2024. https://platform.openai.com/docs/api-reference/chat
4. Matrix.org Foundation, "Matrix Specification," 2023. https://spec.matrix.org/
5. XMPP Standards Foundation, "XMPP: The Definitive Guide," O'Reilly Media, 2009.
6. M. Grieves, "Digital Twin: Manufacturing Excellence through Virtual Factory Replication," white paper, 2014.
7. E. Glaessgen and D. Stargel, "The Digital Twin Paradigm for Future NASA and U.S. Air Force Vehicles," AIAA, 2012.

---

*This white paper is published under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). You are free to share and adapt this material for any purpose, provided appropriate credit is given to the original author.*

*Reference implementation source code is published under the [MIT License](../LICENSE).*
