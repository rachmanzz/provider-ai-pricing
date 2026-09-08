# AI Pricing Sources

List of sources used to collect AI provider pricing data.

## Official Provider Pricing Pages

| Provider | Source Link |
|----------|-------------|
| Z.AI (GLM) | https://docs.z.ai/guides/overview/pricing |
| Cheaper Inference | https://www.cheaperinference.com/#models |
| Together AI | https://www.together.ai/pricing |
| OpenAI | https://openai.com/api/pricing/ |
| Anthropic | https://www.anthropic.com/pricing |
| Google (Gemini) | https://ai.google.dev/pricing |
| Mistral | https://mistral.ai/pricing |
| Cohere | https://cohere.com/pricing |
| DeepSeek | https://api-docs.deepseek.com/quick_start/pricing |
| Replicate | https://replicate.com/pricing |
| Groq | https://groq.com/pricing |
| Fireworks AI | https://fireworks.ai/pricing |

## Best Coding Models (Top 13)

Priority list of models tracked in the catalog for coding tasks. `pricing.md` compares these against each other.

| Rank | Model | Provider | Why |
|------|-------|----------|-----|
| 1 | Claude Sonnet 4.6 | Anthropic | Best code quality + tool use balance |
| 2 | GPT-5.6 Sol | OpenAI | Top-tier reasoning and coding agent |
| 3 | Gemini 3.8 Flash | Google | Fast, cheap, strong coding + 1M context |
| 4 | Claude Opus 4.8 | Anthropic | Max quality for complex refactors |
| 5 | GPT-6 Astra | OpenAI | Frontier coding performance |
| 6 | DeepSeek V4 Pro | DeepSeek | Open-weight, near-frontier, cheap |
| 7 | Kimi K3 | Moonshot AI | Strong agentic coding, big context |
| 8 | GLM-5.3 | Z.AI | Strong coding + affordable long context |
| 9 | Qwen3.8 Max | Alibaba | Open-weight coding leading edge |
| 10 | Grok 4.6 | xAI | Fast coding with large context |
| 11 | MiniMax M3 | MiniMax | Efficient 1M context, cheap coding |
| 12 | Muse Spark 1.3 | Meta | Strong agentic coding, 1M context |
| 13 | GLM-5.3-Flash | Z.AI | Ultra-cheap high-speed coding |

## Guide

- Update the list when adding new providers to the catalog
- Each source link points to the official pricing page
- Scraping logic should reference these links in `knowledge/prd.md`
