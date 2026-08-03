# Agentic Video Assistant

An agent (built with [smolagents](https://github.com/huggingface/smolagents)) that
turns a short idea into a video:

```
User request
   → search_web        (gather real facts, if relevant)
   → write a better video prompt
   → generate_video     (submit job, poll until done, download)
   → answer with the local file path
```

## Project layout

```
agentic-video-assistant/
├── app.py              # entry point - run this
├── agent/               # the agent's "brain": model + tools + prompt
├── tools/                # what the agent can call (time, search, video)
├── services/             # pure API client + polling (no smolagents here)
├── config/                # reads .env into one Settings object
├── ui/                    # Gradio chat interface
├── utils/                 # logger + small helpers
├── tests/                 # unit tests (no real API calls)
└── outputs/videos/         # generated videos land here
```

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure your secrets

```bash
cp .env.example .env
```

Then open `.env` and fill in:

| Variable | What it is | Where to get it |
|---|---|---|
| `MODEL_ID` | Which LLM to use (e.g. `gpt-4o-mini`) | pick any [litellm-supported model](https://docs.litellm.ai/docs/providers) |
| `MODEL_API_KEY` | API key for that LLM provider | OpenAI / Hugging Face / etc. dashboard |
| `AGNES_API_URL` | Base URL of your video generation API | your video provider's docs |
| `AGNES_API_KEY` | API key for the video provider | your video provider's dashboard |

`search_web` needs **no key** (it uses DuckDuckGo).

**Never commit `.env`** - it's already in `.gitignore`. Only commit `.env.example`.

## 3. Run locally

```bash
python app.py
```

Open the printed local URL (default `http://localhost:7860`).

## 4. Run the tests

```bash
python -m pytest tests/ -v
```

## Do you need a database?

**No, not for this scope.** Right now:
- Conversation memory lives in the agent's own memory for the current run (in RAM).
- Generated videos are saved as files in `outputs/videos/`, named with a timestamp.
- Logs are saved as files in `logs/`.

That's enough for a solo demo/portfolio project. You'd only need a real
database (e.g. SQLite to start, Postgres later) if you want to:
- persist conversations **across restarts** or **across users**,
- show a history/gallery of past videos per user,
- support multiple simultaneous users with separate memory (see below).

If you do want that, SQLite is the easiest first step - it's a single
file, no server to run, and Python has it built in (`sqlite3`).

## Deploying (Railway / Render)

This repo includes a `Dockerfile`. Both Railway and Render can build and
deploy it directly from GitHub.

- Set the same variables from `.env` in your host's "Environment Variables" panel.
- Both platforms inject a `$PORT` env var at runtime. Either set
  `GRADIO_SERVER_PORT` to that value in the platform's settings, or edit
  `app.py` to read `PORT` first if set.
- **Railway**: free-tier terms change over time and may require card
  verification depending on your account/region - check current signup
  requirements before committing to it.
- **Render**: has a free web-service tier with cold starts, also subject to change.

## Level it up (ideas for going further)

Roughly ordered from easiest to most impressive:

1. **Video gallery** - list previously generated videos (read the
   `outputs/videos/` folder) in the Gradio UI with a dropdown/gallery.
2. **Per-user memory** - use `gr.State` to give each visitor their own
   `build_agent()` instance instead of one shared global agent, so two
   people using the demo at once don't mix up conversations.
3. **Persist conversations** - add a small `services/storage.py` using
   SQLite to save each run (prompt, facts found, final video path) so
   you can show history later. This is the natural point where a DB
   starts to earn its place.
4. **Multi-agent setup** - split into a "Researcher" agent (search only)
   and a "Director" agent (writes the final prompt + generates video),
   managed by smolagents' `ManagedAgent` pattern. This directly
   demonstrates "multi-agent collaboration", one of the gaps noted in
   the project review.
5. **Style/length options in the UI** - let the user pick a video style
   or duration with Gradio dropdowns, and pass that into the prompt.
6. **Retry with backoff** - if `AgnesRateLimitError` is raised, wait and
   retry automatically instead of failing immediately.
7. **Cache search results** - if the same topic is searched twice in a
   session, reuse the earlier result instead of calling the search API
   again.

## Notes on the "agnes" video API client

`services/agnes.py` uses **placeholder** endpoint paths and field names
(`/v1/videos`, `task_id`, `video_url`, ...). Replace them with your real
video provider's actual API once you pick one - the polling, error
handling, and file-saving logic around it will keep working unchanged.
