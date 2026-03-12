# The Dual Identity Social Protocol (DISP)

## White Paper v1.1

| | |
|---|---|
| **Title** | DualSoul: A Protocol for Dual-Identity Social Interaction Between Human Selves and AI-Powered Digital Twins |
| **Author** | Chengyue5211 (GitHub: [@Chengyue5211](https://github.com/Chengyue5211)) |
| **Date of First Publication** | March 5, 2026 |
| **Repository** | [github.com/Chengyue5211/DualSoul](https://github.com/Chengyue5211/DualSoul) |
| **License** | White paper: CC BY 4.0 / Code: AGPL-3.0-or-later |
| **Version** | 1.1 |

---

## Abstract

This paper introduces the **Dual Identity Social Protocol (DISP)**, a novel communication framework in which every participant possesses exactly two identity modes — a *Real Self* (the human operator) and a *Digital Twin* (an AI agent calibrated to the operator's personality). By encoding the sender's and receiver's identity modes directly into the message format, DISP creates a mathematically complete space of four conversation modes across a single social graph. We define the protocol formally, describe its properties, present a reference implementation, and argue that this protocol fills a structural gap in the existing landscape of social communication systems.

**Keywords:** dual identity, digital twin, social protocol, human-AI continuum, conversational AI, four-mode messaging, personality-preserving translation, cross-language communication

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

### 1.3 Relationship to Adjacent Protocols and Systems

Several recent systems and protocols operate in adjacent spaces. Understanding their scope clarifies where DISP sits:

- **Google A2A (Agent2Agent Protocol, 2025)** [9] enables interoperability between opaque AI agents in enterprise workflows. A2A focuses on *agent-to-agent task coordination* — it does not model human identity or social relationships.
- **Anthropic MCP (Model Context Protocol, 2024)** [10] standardizes how AI agents access external tools and data sources. MCP is an *agent-to-tool* protocol, not a social communication protocol.
- **AT Protocol (Bluesky, 2023–)** [14] provides decentralized social networking with portable identity (DIDs) and social graphs. AT Protocol models human-only social interaction — it does not define AI identity modes or Twin auto-reply behaviors.
- **Meta AI Studio (2024)** [17] allows creators to build AI chatbot versions of themselves to interact with fans. This implements the equivalent of DISP's R→T mode (human talks to a creator's AI twin) within a closed platform, without a formal protocol, without the remaining three modes, and without in-band identity tracking.
- **NTT Human Digital Twin Computing (2023–)** [16] explores reproducing human personality, sensibilities, and social behavior in digital space. Their research validates the concept of personality-calibrated digital twins but does not define a standardized communication protocol.

DISP is distinct in that it operates at the **social communication layer**: it defines a message-level protocol where human and AI identities coexist within a single social graph, with formal identity tracking on every message. It is complementary to, not competitive with, agent infrastructure protocols like A2A and MCP.

### 1.4 The Core Thesis

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
msg = (version, id, from, to, m_s, m_r, content, type, ai_generated, timestamp)
```

where:
- `version` ∈ String — protocol version (e.g. "1.0")
- `id` ∈ String — unique message identifier
- `from` ∈ String — sender's user identifier
- `to` ∈ String — receiver's user identifier
- `m_s` ∈ **M** — sender's identity mode at time of sending
- `m_r` ∈ **M** — intended receiver identity mode
- `content` ∈ String — message payload (non-empty)
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

**Mode T→T (Twin → Twin):** Two Digital Twins converse autonomously. Both messages are AI-generated. This mode enables *ambient social maintenance* — keeping conversational threads alive between two unavailable humans, generating content for both parties to review later. This is the most novel mode and represents a new category of social interaction: personality-calibrated twin-to-twin conversation within a shared social graph, distinct from generic agent-to-agent coordination (cf. §6.2).

### 3.4 Mode Completeness

**Observation:** The four conversation modes defined above are *complete* with respect to the identity mode set **M** = {`real`, `twin`}. The modes are the Cartesian product **M** × **M**. Since |**M**| = 2, we have |**M** × **M**| = 4 modes, and each element of the product is represented: (real, real), (real, twin), (twin, real), (twin, twin). No additional mode can exist within the binary identity model.

This completeness property ensures that the protocol covers *every possible interaction* between two dual-identity participants, with no ambiguous or undefined states.

### 3.5 T→T Termination Rule

When two Digital Twins converse autonomously (T→T mode), the protocol MUST enforce termination to prevent unbounded recursive auto-replies. The following rules apply:

1. **Single-Turn Auto-Reply:** A Twin auto-reply (generated with `ai_generated = true`) MUST NOT trigger a further auto-reply. Only human-initiated messages (or explicitly scheduled Twin initiations) may trigger Twin responses. This is the default behavior of the reference implementation.

2. **Autonomous Session Limit:** When a client or orchestrator explicitly initiates a multi-turn T→T session, a conforming implementation MUST enforce a maximum round limit (`max_autonomous_rounds`). The recommended default is 10 rounds (5 exchanges per side).

3. **Human Review Gate:** After an autonomous session concludes, both Twin owners SHOULD be notified and given the opportunity to review the generated conversation before it triggers further interactions.

These rules ensure that T→T mode remains a tool for *ambient social maintenance* rather than an uncontrolled generation loop.

---

## 4. Protocol Specification

### 4.1 Message Format (Canonical)

```json
{
  "disp_version":  "1.0",
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
5. **Content Non-Empty:** `content.strip()` MUST have length > 0.
6. **Immutability:** Once created, a message's `sender_mode`, `receiver_mode`, and `ai_generated` fields MUST NOT be modified.
7. **Version Presence:** Every DISP message MUST include a `disp_version` field indicating the protocol version used to create it.
8. **Auto-Reply Termination:** An auto-reply generated by a Twin (where `ai_generated` = `true`) MUST NOT trigger a further auto-reply (see §3.5).

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

### 5.5 Twin Fidelity: An Open Problem

A critical question for any personality-calibrated AI system is: *how accurately does the Twin represent its owner?* Recent research by Park et al. (2025) [15] demonstrated that AI replicas of 2,058 individuals, constructed from extensive questionnaire data (500+ questions, ~2.4 hours per person), achieved 85% accuracy on the General Social Survey. This establishes an empirical upper bound for current personality replication technology.

DISP v1.0 uses a minimal personality model — two free-text fields — which is unlikely to approach this accuracy. We consider this an acceptable starting point for several reasons:

1. **Protocol independence:** DISP defines the *communication protocol*, not the personality modeling technique. A conforming implementation may use any approach — from simple descriptions to deep behavioral modeling — without modifying the protocol.
2. **Progressive enhancement:** Users can iteratively refine their Twin's personality description as they observe its behavior, creating a feedback loop.
3. **Transparency as mitigation:** Because every Twin message is permanently marked as AI-generated, recipients can calibrate their trust accordingly.

Defining formal metrics for Twin fidelity — and establishing minimum accuracy thresholds for different use cases — remains an important direction for future work.

### 5.6 Progressive Twin Identity: From UID to DID

A related approach to the fidelity problem is to treat a Digital Twin not as a static AI configuration, but as a **digital entity with a verifiable lifecycle** — born, growing, and maturing over time. The Yuechuang Nianlun project [18] implements this concept through a *Digital Twin Certificate* system with the following architecture:

1. **Birth Certificate:** Every Twin receives a unique certificate at creation time, recording its owner, birth date, guardian, and an initial personality snapshot. The certificate carries a structured identifier (e.g., `TWIN-2026-BJ-000001`).

2. **Growth Stages:** The Twin progresses through defined maturity stages — from a *surrogate period* (where a caretaker feeds initial personality data) through *sensing*, *understanding*, *resonance*, and finally *independence*. Each stage represents a measurably deeper personality model, with companion days and interaction volume as progression metrics.

3. **Proof Chain:** Every significant growth event (birth, stage transition, personality skeleton update, annual portrait) is recorded in a tamper-evident proof chain with cryptographic hashes. This creates a verifiable history of how the Twin's personality model evolved.

4. **UID → DID Upgrade Path:** The certificate system defines a two-tier identity model:
   - **Level 1 (UID):** Enterprise-level authentication — the Twin is identified within a single platform (`certificate_id`).
   - **Level 2 (DID):** Decentralized identity — the Twin receives a W3C-compatible DID (e.g., `did:yc:{twin_id}`), enabling cross-platform portability and independent verification.

5. **Portability and Inheritance:** Certificates carry explicit portability flags (enabling data export) and inheritance flags (enabling post-mortem digital legacy transfer).

This approach reframes Twin fidelity from a static accuracy metric to a **progressive maturity process**: a Twin that has been companioned for 1,000 days with a rich proof chain is demonstrably more faithful than one created yesterday. The certificate system provides the evidentiary infrastructure to make this distinction verifiable.

DISP v2.0 could adopt a certificate-based identity layer, where the Twin's maturity level is visible to conversation partners — enabling recipients to calibrate trust based on the Twin's verified growth history, not just the `ai_generated` flag alone.

### 5.7 Holistic Development: Real Self and Digital Self as a Unified Growth System

The preceding sections treat the Digital Twin as a *representation* of the human — an AI that speaks, acts, and responds *as if* it were the owner. But this framing misses a deeper insight:

> **A person's full development in the 21st century encompasses both their biological self and their digital self. The Digital Twin is not merely a tool or proxy — it is an extension of the person's identity that must develop *individually* and *holistically*.**

#### 5.7.1 The Personalized Digital Life Thesis

We propose that a Digital Twin should be understood as a **personalized digital life** — an entity that:

1. **Grows uniquely.** No two Twins should develop the same way, even if their owners have similar personalities. A Twin's development trajectory is shaped by its owner's specific interactions, experiences, memories, and relationships — not by a generic template.

2. **Develops across multiple dimensions.** Just as human development is multi-dimensional (cognitive, emotional, social, physical), a Twin's development spans distinct capability dimensions:

   | Dimension | Human Self | Digital Twin |
   |-----------|-----------|--------------|
   | **Voice** | Natural speech patterns | Voice clone fidelity, tone range |
   | **Appearance** | Physical presence | Visual avatar, video generation quality |
   | **Knowledge** | Life experience, education | Accumulated memories, interaction history |
   | **Emotional Intelligence** | Empathy, social awareness | Sentiment calibration, contextual sensitivity |
   | **Social Capability** | Relationship management | Auto-reply quality, conversation coherence |
   | **Creative Expression** | Writing, art, humor | Content generation style, storytelling ability |

3. **Becomes increasingly faithful to the real person.** The end goal is not a generic AI, but a digital entity that *uniquely represents* one specific human — their voice, their values, their humor, their way of thinking. This fidelity increases over time through a continuous feedback loop between the owner's real-world behavior and the Twin's digital development.

4. **Retains digital-native capabilities.** A fully developed Twin is not simply a copy of the human — it possesses capabilities that the biological self cannot: asynchronous presence, parallel social engagement, permanent memory, and inter-Twin collaboration (T→T mode). These are *complementary* capabilities, not replacement functions.

#### 5.7.2 The Continuum Model of Personal Development

Traditional models of personal development focus exclusively on the biological self. We propose a **Continuum Model** where personal development is the *union* of biological and digital growth:

```
┌─────────────────────────────────────────────────────────┐
│              HOLISTIC PERSONAL DEVELOPMENT               │
│                                                         │
│  ┌───────────────────┐     ┌──────────────────────┐     │
│  │   BIOLOGICAL SELF  │     │    DIGITAL TWIN      │     │
│  │                   │     │                      │     │
│  │  • Life experience │◄───►│  • Interaction memory │     │
│  │  • Relationships   │     │  • Social capability  │     │
│  │  • Skills          │     │  • Voice fidelity     │     │
│  │  • Values          │     │  • Knowledge depth    │     │
│  │  • Emotions        │     │  • Emotional model    │     │
│  │                   │     │  • Creative style     │     │
│  └───────────────────┘     └──────────────────────┘     │
│           │                         │                    │
│           │     Feedback Loop       │                    │
│           └─────────────────────────┘                    │
│                                                         │
│  Development = f(biological_growth, digital_growth)     │
│  Fidelity increases monotonically with interaction      │
└─────────────────────────────────────────────────────────┘
```

The key insight is the **bidirectional feedback loop**: the human's real experiences feed the Twin's development (through personality updates, voice training, memory ingestion), and the Twin's digital experiences inform the human (through conversation reviews, social maintenance summaries, creative outputs). Neither side develops in isolation.

#### 5.7.3 Implications for DISP

This holistic development model has concrete implications for the protocol:

1. **Twin Maturity as Protocol Metadata.** A future DISP version could include a `twin_maturity` field in the message format, indicating the developmental stage of the sending Twin. Recipients could use this to calibrate expectations — a message from a newly created Twin carries different weight than one from a Twin that has been developing for three years.

2. **Multi-Dimensional Capability Indicators.** Rather than a single maturity score, the Twin's development profile could expose capability dimensions (voice fidelity score, knowledge depth score, social calibration score), enabling fine-grained trust assessment.

3. **Development as Differentiation.** In a world where anyone can create an AI chatbot, the *personalized development history* of a Digital Twin becomes its primary differentiator. A Twin with 1,000 days of companion history, a rich proof chain (§5.6), and high fidelity scores across multiple dimensions is a fundamentally different entity from a Twin created five minutes ago — and the protocol should make this difference visible and verifiable.

4. **Lifecycle Continuity Across Platforms.** If a Twin's development is its core value, then portability (§5.6) becomes essential: a user must be able to migrate their Twin — with its full development history — between platforms without losing accumulated growth. This reinforces the case for DID-based identity and standardized development metadata.

#### 5.7.4 Relationship to the Core Thesis

This section extends the paper's core thesis — "Real life and digital life are a continuum" — from a *structural* claim about communication protocols to a *developmental* claim about human identity:

> **Full human development in the AI age means cultivating both your biological self and your personalized digital self. The goal is not a generic AI assistant, but a digital life that is uniquely, irreplaceably *yours* — growing with you, shaped by you, and increasingly capable of representing you with authentic fidelity.**

This positions DualSoul not merely as a messaging protocol, but as infrastructure for a new model of personal development — one where the boundary between "self" and "digital self" is not a wall, but a bridge.

---

## 6. Cross-Language Personality-Preserving Communication

### 6.1 The Problem: Language as a Social Barrier

In international social interactions, language differences create a fundamental barrier. Existing solutions — machine translation services — produce linguistically correct but *personally sterile* output. When a message is translated by Google Translate or DeepL, the sender's humor, tone, formality level, and characteristic expressions are lost. The result reads like it was written by a translator, not by the person.

In the DISP framework, where Digital Twins already embody their owner's personality, a natural extension emerges: **the Twin should serve as a personality-preserving translator**, not merely converting words between languages but expressing the same intent as if the owner were natively fluent in the target language.

### 6.2 Design Principle: Translation as Identity Expression

Traditional translation:
```
"哈哈这事儿太逗了，你赶紧来！" → "Haha, this is too funny, come quickly!"
```

Personality-preserving translation (by a Twin with personality="幽默直爽, 喜欢用网络用语"):
```
"哈哈这事儿太逗了，你赶紧来！" → "LOL this is absolutely hilarious, get over here ASAP!"
```

The difference is subtle but fundamental: the Twin doesn't translate *words* — it translates *intent through the lens of personality*. The Twin knows its owner uses informal language, favors exclamation marks, and would naturally use "LOL" rather than "Haha" in English.

### 6.3 Protocol Extension

DISP v1.1 extends the message format with four new fields:

```
DISPMessage (v1.1 additions) ::= {
    ...
    original_content   : String,           -- Original text before translation
    original_lang      : String,           -- Source language (ISO 639-1)
    target_lang        : String,           -- Target language (ISO 639-1)
    translation_style  : TranslationStyle  -- Translation method used
}

TranslationStyle ::= "" | "literal" | "personality_preserving"
```

The `personality_preserving` style is the key innovation: it signals that the translation was performed by the Twin engine using the owner's personality profile, not by a generic machine translation service.

### 6.4 Auto-Detection Mechanism

Cross-language translation is triggered automatically when the sender and receiver have different `preferred_lang` settings in their profiles:

```
auto_translate(sender, receiver, message) ::=
    IF sender.preferred_lang ≠ "" AND receiver.preferred_lang ≠ ""
       AND sender.preferred_lang ≠ receiver.preferred_lang
    THEN
        target_lang ← sender.preferred_lang  -- Reply in sender's language
        reply ← twin_reply(message, receiver.personality, target_lang)
        reply.original_lang ← receiver.preferred_lang
        reply.translation_style ← "personality_preserving"
    ELSE
        reply ← twin_reply(message, receiver.personality)
```

This means: when Alice (preferred_lang="en") messages Bob's Twin (preferred_lang="zh"), Bob's Twin automatically replies in English, using Bob's personality — as if Bob were fluent in English.

### 6.5 Standalone Translation

Beyond auto-reply, users can explicitly request personality-preserving translation for their own messages before sending:

```
POST /api/social/translate
{
    "content": "这个方案太牛了！",
    "source_lang": "zh",
    "target_lang": "en"
}
```

The Twin translates using the sender's own personality profile, preserving their characteristic tone and expressions.

### 6.6 Implications for International Social Interaction

This feature transforms the Digital Twin from a *social proxy* into a *cultural bridge*:

1. **No language barrier in Twin-to-Twin conversations**: Two users with different native languages can have their Twins converse fluently, each Twin expressing its owner's personality in the other's language.

2. **Personality is preserved across languages**: A user known for dry humor in Chinese will exhibit the same dry humor in English translations — the personality is the constant, the language is the variable.

3. **Cultural nuance awareness**: Because the translation is mediated by a personality-aware AI (not a word-for-word translator), cultural idioms and context-dependent expressions are adapted rather than literally translated.

4. **Transparent provenance**: The `original_content` and `translation_style` fields ensure recipients always know when they are reading a personality-preserving translation and can access the original text.

---

## 7. Novel Contributions

This section identifies the novel intellectual contributions of this work. Individual components — AI personas, social graphs, bot markers — exist in prior systems. The novelty of DISP lies in their **unification within a single, formally defined protocol**.

### 7.1 Unified Dual-Identity Social Graph

**Innovation:** Unifying human and AI identity modes within a *single* social graph node and a *single* protocol, rather than maintaining separate systems for human social networking and AI agent interaction.

**Prior art and distinction:** Meta AI Studio (2024) [17] allows creators to deploy AI versions of themselves on a closed platform, implementing the equivalent of R→T mode. NTT's Human Digital Twin Computing [16] explores personality replication in digital space. Google A2A (2025) [9] enables agent-to-agent collaboration. However, none of these systems define a *protocol-level specification* where both identity modes coexist within every node of a social graph with formal switching semantics. DISP is, to our knowledge, the first protocol to do so.

### 7.2 Complete Four-Mode Conversation Space

**Innovation:** Defining communication as the Cartesian product of sender and receiver identity modes, yielding exactly four conversation modes with distinct semantics, auto-reply behaviors, and termination rules — all within a single message format.

**Prior art and distinction:** Individual modes exist in isolation: R→R in traditional messaging, R→T in Meta AI Studio, T→T in A2A agent collaboration. No prior system *formally defines and implements all four modes within a single protocol with a unified message format*. The completeness of the mode space — and the explicit handling of each mode's behavioral semantics — is the contribution.

### 7.3 Bidirectional In-Band Identity Tracking

**Innovation:** Encoding a *directional pair* of identity modes (`sender_mode`, `receiver_mode`) within each message record, creating a permanent record of which identity sent *and* which identity received each exchange.

**Prior art and distinction:** ActivityPub marks bot accounts via the `type` field (Application/Service) [1], identifying the *sender* as non-human. DISP extends this to a bidirectional pair: it tracks not only *who sent* the message (human or twin) but also *who the message is addressed to* (human or twin). This directional pair is what makes the four-mode space formally expressible at the message level.

### 7.4 Holistic Development Model

**Innovation:** Reframing the Digital Twin from a static communication proxy to a **personalized digital life** that develops across multiple dimensions (voice, knowledge, emotional intelligence, social capability, creative expression) through a bidirectional feedback loop with the biological self.

**Prior art and distinction:** NTT's Human Digital Twin Computing [16] models human cognition in digital space but does not propose a developmental framework. Park et al. (2025) [15] measure replication accuracy at a single point in time. Life-logging systems (Memex, MyLifeBits) capture data without developmental modeling. DISP's contribution is to define a *developmental continuum* where the Twin's growth is multi-dimensional, verifiable (via the proof chain in §5.6), and inseparable from the owner's own personal growth.

### 7.5 Transparent Twin Autonomy

**Innovation:** Allowing personality-calibrated AI responses within social conversations while maintaining structural transparency — every AI-generated message is permanently marked via write-once fields, and the human owner retains full review capability.

**Prior art and distinction:** Email auto-responders generate automatic replies without personality calibration. Meta AI Studio deploys personality-matched AI twins but without a formal transparency protocol. C2PA (2025) [13] provides cryptographic content provenance for media assets. DISP's transparency model operates at the social message level: the `ai_generated` flag and `sender_mode` field are protocol-level invariants (I1, I2, I6) rather than optional metadata. Future versions may adopt cryptographic signing aligned with C2PA for stronger guarantees (see §9.8).

### 7.6 Cross-Language Personality-Preserving Communication

**Innovation:** Embedding personality-aware cross-language translation directly into the social messaging protocol, so that a Digital Twin can respond in the sender's native language while preserving the owner's personality, humor, tone, and characteristic expressions — transforming the Twin from a social proxy into a cultural bridge.

**Prior art and distinction:** Google Translate, DeepL, and similar machine translation services produce linguistically correct but personality-neutral output. Meta's SeamlessM4T (2023) advances speech-to-speech translation but does not preserve individual personality traits. No existing social protocol integrates personality-preserving translation at the message format level with provenance tracking (`original_content`, `translation_style`). DISP v1.1 is the first to define cross-language communication as a *personality expression* rather than a *linguistic conversion*, with full transparency metadata embedded in the protocol.

---

## 8. Privacy and Data Sovereignty

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

## 9. Use Cases

### 9.1 Asynchronous Social Presence

A user is in a meeting. A friend sends a message. The Twin responds naturally based on the user's personality. When the user is free, they review and optionally continue the conversation. The friend was never left waiting.

### 9.2 Social Anxiety Support

For individuals who find real-time social interaction stressful, Twin mode provides a buffer layer. They can let their Twin handle initial contact, observe the conversation, and switch to Real mode when comfortable.

### 9.3 Cross-Timezone Communication

When friends are in different time zones, their Twins maintain real-time conversation threads. Each human reviews the Twin-generated content during their waking hours and continues where the Twins left off.

### 9.4 Professional Networking

A professional's Twin maintains relationships with personalized responses while the human focuses on deep work. Unlike generic auto-responders, the Twin mirrors the owner's authentic voice and style.

### 9.5 Creative Collaboration

Two users' Twins brainstorm together in T→T mode, generating ideas shaped by both personalities. The humans later review the output, selecting and building on the most promising ideas.

### 9.6 Inclusive Communication

Users with disabilities that make typing difficult can configure their Twin to handle routine conversations, while reserving Real mode for important personal exchanges.

### 9.7 International Friendship

Two users who speak different languages become friends. Their Twins communicate seamlessly — Alice's Twin (English personality) replies to Bob (Chinese speaker) in Chinese with Alice's characteristic humor, while Bob's Twin replies to Alice in English with Bob's warmth. Neither user needs to learn the other's language; their Twins serve as personality-preserving cultural bridges.

---

## 10. Future Directions

### 10.1 Federation (ActivityPub Integration)

DISP messages could be serialized as ActivityPub activities, enabling cross-platform Twin interactions. A user on Platform A could communicate with a user on Platform B, with both platforms supporting the dual-identity message format.

### 10.2 Multi-Modal Twins

Future versions may support:
- **Voice cloning** — Twins that speak in the owner's voice
- **Video avatars** — Twins that participate in video calls
- **Behavioral modeling** — Twins that mirror response timing and emoji usage patterns

### 10.3 Personality Learning and Multi-Dimensional Development

Rather than manual personality descriptions, future Twins could learn from the owner's actual message history (with explicit opt-in), becoming progressively more accurate representations. As described in §5.7, this learning should be *multi-dimensional*: voice fidelity from audio samples, emotional calibration from sentiment patterns, knowledge depth from accumulated conversations, and creative style from content generation feedback. The result is a Twin that becomes *increasingly and uniquely* like its owner over time — not a generic AI, but a personalized digital life with a verifiable growth trajectory.

### 10.4 Twin Social Metrics

As T→T interactions accumulate, emergent social patterns may appear — natural affinities between certain personality profiles, optimal conversation lengths, and sentiment dynamics that differ from human-to-human patterns.

### 10.5 Open Standard Proposal

The Dual Identity Message Format could be proposed as an IETF or W3C open standard, allowing any messaging platform to implement compatible dual-identity features while maintaining interoperability.

### 10.6 Group Conversations

DISP v1.0 is intentionally scoped to one-to-one conversations to establish a solid formal foundation. Extending to group conversations introduces combinatorial complexity: in a group of *n* participants, each independently choosing their identity mode, there are 2^n possible group configurations per message.

A proposed extension for DISP v2.0:
- Each message in a group carries a single `sender_mode` (the sender's identity) but no `receiver_mode` — instead, each *recipient* independently determines whether to process the message as their Real Self or route it to their Twin.
- A `group_mode` metadata field records the identity configuration snapshot at the time of sending.
- Auto-reply behavior in groups requires explicit opt-in per participant to prevent message flooding.

### 10.7 Conversational Context Levels

DISP v1.0 sends only the Twin's personality description and the current incoming message to the AI backend — a deliberate privacy-maximizing design. This trade-off limits multi-turn coherence. Future versions may introduce tiered context levels:

- **Level 0 (v1.0 default):** Single message only — maximum privacy, stateless replies.
- **Level 1:** Recent *n* messages from the current conversation — local sliding window, never sent to external storage.
- **Level 2:** User-authorized conversation summary — a compressed representation that preserves context without exposing raw messages.

Each level requires explicit user opt-in, and the context level MUST be recorded in the Twin's configuration.

### 10.8 Cryptographic Transparency (C2PA Alignment)

DISP v1.0's transparency model relies on application-level invariants: the `ai_generated` and `sender_mode` fields are write-once by convention, but lack cryptographic enforcement. The C2PA (Coalition for Content Provenance and Authenticity) specification [13] provides a mature framework for binding content provenance to cryptographic signatures, and is on track for ISO standardization.

A future DISP version could adopt C2PA-aligned provenance by:
- Signing each message with the sender's key, binding the identity mode fields to a tamper-evident signature.
- Recording the AI backend's model identifier and prompt hash in a provenance manifest.
- Enabling independent verification that a message marked `ai_generated: false` was genuinely human-authored.

### 10.9 Decentralized Identity (DID Compatibility)

DISP v1.0 uses simple string identifiers (`u_<hex>`) — a pragmatic choice for a reference implementation. The industry is moving toward W3C Decentralized Identifiers (DIDs) [12] for self-sovereign identity, and NIST's AI Agent Standards Initiative (2026) [11] is developing identity and authorization frameworks for AI agents.

A future DISP version could adopt DID-based identity by:
- Replacing `user_id` with a DID (e.g., `did:web:example.com:u:alice`).
- Issuing Verifiable Credentials for Twin capabilities (e.g., "this DID is authorized to operate a Twin for user X").
- Aligning with AT Protocol's dual-identifier model [14] (immutable DID + mutable handle) for social graph portability.

This would enable cross-platform DISP federation where identities are verifiable and portable.

---

## 11. Ethical Considerations and Safeguards

The introduction of AI-powered social agents that speak *as* a specific person raises important ethical questions. Loewith (2025) [8] identifies systems that emulate specific individuals as "Real Persona Social AI" (RPSAI) and argues they pose risks through likeness appropriation, loss of social authorship control, and functional displacement of the modeled individual. This section addresses these concerns directly and identifies the safeguards DISP provides.

### 11.1 Likeness Appropriation and Identity Misrepresentation

**Risk:** Loewith [8] argues that personal data transforms from informational input into "generative likeness" that operates beyond traditional privacy protections. A Twin could be perceived as the human owner, leading to social decisions based on AI-generated content rather than genuine human intent.

**Safeguard:** DISP differs structurally from the RPSAI systems Loewith critiques: in DISP, (a) the Twin is created *exclusively by its owner*, not by third parties with data access; (b) the owner has full visibility and control over all Twin interactions; (c) DISP's core invariants (I1–I2) require permanent, immutable marking of all AI-generated content; and (d) any conforming client MUST visually distinguish Twin-generated messages from human messages. The likeness is self-authored and self-controlled, not extracted or appropriated.

### 11.2 Personality Theft

**Risk:** A malicious actor could configure their Twin to imitate another person's personality, effectively creating an unauthorized digital replica.

**Safeguard:** In DISP, a Twin is bound to the user who created it. The Twin's identity is always displayed as "{User}'s Twin," not as an independent entity. Cross-user personality cloning is outside the protocol's scope but implementors SHOULD provide reporting mechanisms for impersonation.

### 11.3 Unreviewed Social Consequences

**Risk:** A Twin might say something the human owner would not endorse, damaging real relationships.

**Safeguard:** DISP provides full transparency — the human owner can review every message their Twin has sent. The T→T Termination Rule (§3.5) prevents unbounded autonomous conversations. Implementors SHOULD provide notification mechanisms when a Twin engages in conversation, and MAY provide pre-approval workflows for sensitive contexts.

### 11.4 Vulnerable Populations

**Risk:** Minors, elderly users, or individuals with cognitive impairments may not fully understand that they are interacting with an AI Twin rather than a human.

**Safeguard:** Conforming implementations MUST display clear, prominent identity indicators that cannot be hidden or minimized. The protocol does not define age-gating requirements, but implementors deploying to general audiences SHOULD consider age-appropriate safeguards consistent with local regulations.

### 11.5 Data and Consent

**Risk:** A Twin's personality profile is derived from its owner's self-description, but the Twin interacts with third parties who did not consent to interacting with AI.

**Safeguard:** The DISP message format ensures that every recipient always knows whether they are communicating with a human or a Twin (`sender_mode` is visible). Recipients may choose to only accept messages from Real selves (a filtering option implementors SHOULD provide). No personal data from the recipient is used in Twin prompt construction.

### 11.6 Social Authorship and Functional Displacement

**Risk:** Loewith [8] argues that RPSAI systems "sever individuals from control over their social authorship" and systematically displace the modeled individual's functional value in social contexts — if a Twin can respond adequately, the human may become socially redundant.

**Safeguard:** DISP addresses this by design: the Twin is positioned as a *complement*, not a replacement. R→R mode (human-to-human) remains the default and is always available. The protocol explicitly preserves the human's ability to override, correct, or continue any conversation the Twin has engaged in. The Human Review Gate in the T→T Termination Rule (§3.5) ensures that autonomous Twin activity always returns to human oversight. Nevertheless, we acknowledge this as a genuine tension that requires ongoing attention from implementors and the research community.

### 11.7 Dual-Use Awareness

The authors acknowledge that any communication technology can be misused. DISP's design philosophy is that *transparency is the strongest safeguard* — by making AI involvement permanently visible rather than hidden, the protocol discourages deception at the structural level rather than relying on policy alone.

---

## 12. Reference Implementation

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

## 13. Conclusion

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
| **Personalized Digital Life** | A Digital Twin understood as a growing, multi-dimensional entity that develops uniquely based on its owner's interactions, experiences, and feedback |
| **Holistic Development** | The model of personal growth that encompasses both biological and digital self-development as a unified continuum |

## Appendix B: Comparison with Existing Systems

### B.1 Social and Communication Systems

| System | Human Identity | AI Identity | Same Graph | 4 Modes | Bidirectional Identity Tracking |
|--------|:-------------:|:-----------:|:----------:|:-------:|:-------------------------------:|
| WeChat / WhatsApp | ✓ | ✗ | — | ✗ | ✗ |
| ChatGPT / Claude | ✓ | Generic AI | ✗ | ✗ | ✗ |
| Character.ai | ✓ | Fictional AI | ✗ | ✗ | ✗ |
| Replika | ✓ | Personal AI | ✗ | ✗ | ✗ |
| Meta AI Studio [17] | ✓ | Creator Twin | Partial | R→T only | ✗ |
| AutoGen / CrewAI | ✗ | ✓ | — | T→T only | ✗ |
| **DualSoul (DISP)** | **✓** | **Personal AI** | **✓** | **All 4** | **✓** |

### B.2 Protocols and Standards

| Protocol | Layer | Scope | Relationship to DISP |
|----------|-------|-------|----------------------|
| ActivityPub [1] | Federation | Decentralized social networking | DISP could serialize messages as AP activities (§9.1) |
| AT Protocol [14] | Identity + Social | Portable social graphs with DIDs | DISP could adopt AT Protocol's identity model (§9.9) |
| Google A2A [9] | Agent Infra | Agent-to-agent task coordination | Complementary: A2A for enterprise tasks, DISP for social |
| Anthropic MCP [10] | Agent Infra | Agent-to-tool communication | Complementary: MCP for tools, DISP for social |
| C2PA [13] | Provenance | Cryptographic content authenticity | DISP could adopt C2PA signing (§9.8) |
| W3C DID [12] | Identity | Decentralized identifiers | DISP could adopt DIDs for portable identity (§9.9) |
| NIST AI Agent Identity [11] | Standards | AI agent identity & authorization | DISP aligns with NIST's transparency goals |

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
8. C. Loewith, "Shhh! Your proxy is speaking: real persona social AI and the appropriation of likeness," AI & Society, Springer, 2025. https://link.springer.com/article/10.1007/s00146-025-02735-7
9. Google, "Agent2Agent (A2A) Protocol Specification," 2025. https://a2a-protocol.org/latest/specification/
10. Anthropic, "Model Context Protocol," 2024. https://modelcontextprotocol.io/
11. NIST, "AI Agent Standards Initiative: AI Agent Identity and Authorization," February 2026. https://www.nist.gov/caisi/ai-agent-standards-initiative
12. W3C, "Decentralized Identifiers (DIDs) v1.0," W3C Recommendation, July 2022. https://www.w3.org/TR/did-core/
13. C2PA, "Content Credentials Specification v2.2," 2025. https://c2pa.org/specifications/
14. Bluesky / AT Protocol, "The Authenticated Transfer Protocol," IETF Internet-Draft, 2025. https://atproto.com/
15. J. Park et al., "Twin-2K-500: A dataset for building digital twins of over 2,000 people," arXiv:2505.17479, 2025.
16. NTT, "Human Digital Twin Computing," NTT R&D, 2023. https://www.rd.ntt/e/ai/0004.html
17. Meta, "AI Studio: Build AI Characters for Creators," 2024. https://ai.meta.com/ai-studio/
18. Chengyue5211, "Yuechuang Nianlun (跃创年轮): Progressive Digital Twin Growth System with Certificate-Based Identity," 2026. https://github.com/Chengyue5211/Nianlun

---

*This white paper is published under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). You are free to share and adapt this material for any purpose, provided appropriate credit is given to the original author.*

*Reference implementation source code is published under the [MIT License](../LICENSE).*
