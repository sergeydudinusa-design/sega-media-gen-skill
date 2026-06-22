# media-gen

Local image and image-to-video pipeline using Fal.ai. A lightweight, no-subscription alternative to hosted gen UIs like Higgsfield: you bring your own Fal key and pay per generation.

## What it does

You describe media casually ("a photo of a dog swimming with a tennis ball"). Claude refines the prompt, picks the current best model from `models.json`, generates the image via Fal.ai, saves it to a dated local folder, and asks if you want to animate it. If yes, it conversationally collects a motion prompt, duration, and resolution, then generates the video.

All artifacts (`prompt.md`, `image-NN.png`, `video-NN.mp4`) live in one folder per generation.

## Install

This skill is a Claude Code [agent skill](https://docs.claude.com/en/docs/claude-code/skills). Drop the `media-gen` folder into your skills directory and Claude will pick it up automatically.

1. **Place the folder:**
   - Mac/Linux: `~/.claude/skills/media-gen/`
   - Windows: `C:\Users\<you>\.claude\skills\media-gen\`

2. **Get a Fal key.** Sign up at https://fal.ai and copy your API key from the dashboard.

3. **Set the env var (one-time):**
   - Windows: `setx FAL_KEY "your-key-here"`, then **close and reopen your terminal** (`setx` doesn't apply to the current session).
   - Mac/Linux: add `export FAL_KEY="your-key-here"` to `~/.zshrc` (or `~/.bashrc`), then `source ~/.zshrc`.

   The skill reads `FAL_KEY` from your environment at runtime. It is never stored in any file in this folder.

4. **Install the SDK:**
   ```
   pip install fal-client
   ```

5. **Test it.** In any Claude Code session, say:
   > generate a photo of a single red apple on a white background

   Claude should invoke this skill and run end-to-end.

## How to use it

Just talk to Claude in any session. Triggers:
- *"generate a photo of ..."*
- *"make me an image where ..."*
- *"create a video of ..."*
- *"turn this image into a video"*

Claude reads `SKILL.md`, refines the prompt, picks the model, runs `scripts/generate.py`, and saves to `~/Documents/Media Gen/<date>-<slug>/`.

## Updating the model registry

`models.json` is the source of truth for "current best." Two ways to update:

**Manual:** Edit the file. Bump `default` to the new winner. Update `last_updated`.

**Assisted:** In any Claude session, say *"check fal.ai for new image and video models and update media-gen registry."* Claude will WebFetch fal.ai/models, compare, propose a diff, and write the update on your approval.

## Configuration

Edit `config.json` to change the output root directory. Default is `~/Documents/Media Gen`. Tilde and env vars expand.

## File structure

```
media-gen/
├── SKILL.md            # Workflow instructions Claude reads
├── README.md           # This file
├── config.json         # Output dir + future config
├── models.json         # Curated registry of "current best" Fal models
└── scripts/
    └── generate.py     # CLI: image | video subcommands
```

## Troubleshooting

| Error | Fix |
|---|---|
| `FAL_KEY not set` | `setx FAL_KEY "..."` (Windows) or export in `~/.zshrc` (Mac), then restart terminal |
| `ModuleNotFoundError: fal_client` | `pip install fal-client` |
| `404` on a `fal_id` | Model slug drifted on Fal. Open https://fal.ai/models, find the new slug, update `models.json` |
| `couldn't resolve output_path` | Fal changed the response schema for that model. Check the raw result printed in stderr, update the `output_path` in `models.json` (e.g. `images[0].url` vs `image.url` vs `video.url`) |
| Generation just hangs | Fal queue can be slow. Image gens usually under 30s, videos 1 to 3 min. If over 5 min, kill and retry |

## Cost reality (2026 estimates)

- Nano Banana Pro: ~$0.04 per image
- Seedance 2.0 Pro 5s: ~$0.40 to $0.60 per video
- Kling v3 Pro 5s: ~$0.50 to $0.95 per video

At a light cadence (a handful of images plus 1 to 2 videos per week), you're looking at a few dollars a month, pay-as-you-go instead of a flat subscription. Verify current pricing at fal.ai/pricing. These are estimates, not contracts.
