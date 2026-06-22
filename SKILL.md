---
name: sega-media-gen
description: Generate and upscale AI images and videos via MuAPI using a curated registry of best-in-class models. Use whenever the user asks to create, generate, make, render, or produce a photo, image, picture, or video. Phrases like "make me an image of...", "generate a video of...", "create a photo where...", "I want a picture of...", "turn this into a video", "text to video". Also use to upscale or enhance an existing image to HD ("upscale this", "make this HD"). Workflow refines the prompt with reasoning, picks the current best model from models.json, generates locally to a dated folder, and conversationally offers to animate the image into video.
---

# Media Gen Skill

Local image and image-to-video pipeline via MuAPI. You own the pipeline; models are swappable via `models.json`. No vendor lock-in, no bloated UIs.

> **Path note:** Examples below use the Mac/Linux script path `~/.claude/skills/media-gen/scripts/generate.py`. On Windows, substitute your full path.

## Operating principles

1. **Refine the prompt before sending it.** The user's casual description is the brief, not the prompt. Expand it into a strong 2-4 sentence prompt: lighting, composition, lens/camera language, environment, mood.
2. **Pick the model from `models.json`.** Use `image.default` unless the user specifies. Mention model age if the registry is stale (>30 days).
3. **Be conversational, not form-driven.** Ask one question at a time, accept defaults.
4. **Save everything locally.** Each generation gets its own dated folder.
5. **Don't auto-animate.** Always ask "want to turn this into a video?" first. Never assume.
6. **Quote video cost before running.** MuAPI bills video by the second. Before any `generate.py video` call, read `unit_price_per_second_usd` from `models.json`, compute `price x duration`, state it, and wait for explicit yes. Default duration is **5s**, never 10s. Only go to 10s after user approves the 5s concept. Image gen is cheap and runs autonomously.
7. **Reference images for character consistency.** Pass earlier output images via `--input-image` to lock character/style. See "Character consistency" section.

## Workflow

### Step 1: Read user intent

Extract from the user's description:
- **Subject and action**
- **Implicit style cues** (photo, illustration, cinematic, etc.)
- **Working title**: 3-5 word kebab-case slug (`dog-swimming-tennis-ball`). Derive it, don't ask.

### Step 2: Refine the prompt

Show the refined prompt. Ask: **"Run this, or want to adjust?"** Accept user edits as source of truth.

### Step 3: Pick the model

Read `models.json`. Use `image.default` unless the user specifies.

If `last_updated` in models.json is more than 30 days old, mention it once: *"Model registry was last updated [date]. Want me to refresh it?"* Don't nag.

### Step 4: Generate the image

```bash
python ~/.claude/skills/media-gen/scripts/generate.py image \
  --prompt "<refined prompt>" \
  --title "<working-title>" \
  [--model <model-key>] \
  [--aspect-ratio "16:9"] \
  [--input-image "<ref-path>" ...]
```

Supported aspect ratios: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`. Maps to pixel sizes; default is the model's `default_args.size`.

The script prints a JSON line with `image_path` and `folder`. Display the local path to the user.

**Error handling:**
- `MUAPI_KEY not set` → tell user to add `export MUAPI_KEY="<key>"` to `~/.zshrc` and `source ~/.zshrc`. Get the key from muapi.ai dashboard.
- `requests not installed` → `pip install requests`
- HTTP 404 on endpoint → the endpoint slug in models.json drifted. Fetch `https://api.muapi.ai/api/v1/models` (no auth) to find the current slug.

### Step 5: Offer animation

After image saves, ask: **"Want to turn this into a video?"**

If yes, collect (one question at a time):
- **Motion prompt**: what happens in the video? Different from image prompt. ("The dog paddles forward, water splashing, slight camera dolly in.")
- **Duration**: default **5s**. Don't propose 10s first.

Quote the cost:
1. Read `unit_price_per_second_usd` for the chosen model.
2. Say: *"{model} = ${price}/s × {duration}s = ${total}."*
3. If field is missing or stale, fetch `https://muapi.ai/docs/{endpoint}` before quoting.
4. Ask: **"OK to run at this cost?"** Wait for explicit yes.

Once approved:

```bash
# Image-to-video (I2V) — pass --image:
python ~/.claude/skills/media-gen/scripts/generate.py video \
  --image "<image_path>" \
  --prompt "<motion prompt>" \
  --title "<working-title>" \
  --folder "<folder from step 4>" \
  --duration 5 \
  [--model <model-key>]

# Text-to-video (T2V) — omit --image:
python ~/.claude/skills/media-gen/scripts/generate.py video \
  --prompt "<video prompt>" \
  --title "<working-title>" \
  --folder "<folder>" \
  --duration 5 \
  --model <t2v-model-key>
```

T2V models are in `models.json` under `video` section — same section as I2V. Look for models without "image-to-video" in their name (e.g. `kling-v3.0-pro-text-to-video`, `veo3.1-text-to-video`, `wan2.7-text-to-video`). When the user asks for T2V and hasn't yet generated an image, skip step 4 and go straight to video with a T2V model.

## Upscaling images

Upscale an existing image to higher resolution. Runs autonomously (no cost quote needed).

```bash
python ~/.claude/skills/media-gen/scripts/generate.py upscale \
  --input "<path to source image>" \
  [--model <model-key>] \
  [--title <slug>]
```

**Note:** MuAPI provides image upscaling only. Video upscaling is not available via this skill.

## Character consistency

Pass earlier output images as references via `--input-image` to preserve character, face, or style.

`flux-dev` accepts a single reference image via `--input-image` (it's passed as the `image` field for i2i generation). If you need stronger identity preservation, pass the anchor image and use a prompt like *"the same person from the reference image, now [new action / new setting]"*.

**Workflow:**
1. Generate the "anchor" (establishing shot). Save the path.
2. For subsequent generations of the same character:
   ```bash
   python ~/.claude/skills/media-gen/scripts/generate.py image \
     --prompt "the same woman from the reference image, now walking through a rainy Tokyo street at night" \
     --title "campaign-scene-2" \
     --input-image "<path to anchor image-01.png>"
   ```
3. Don't redescribe the face — let the reference carry it. Describe the new scene.

**When to use:** Multi-shot campaigns, Reels where the same person appears in different scenes.

**When NOT to use:** One-off images (slows gen), when you want a different person/style.

### Output structure

```
~/Documents/Media Gen/2026-06-22-dog-swimming-tennis-ball/
├── prompt.md            # metadata: prompts, endpoints, params, timestamps
├── image-01.png
└── video-01.mp4         # only if video step ran
```

## Updating the model registry

When the user asks to refresh models:

1. Fetch live catalog: `GET https://api.muapi.ai/api/v1/models` (no auth needed).
2. Compare against `models.json`, flag new top-tier additions.
3. Propose updates: bump `default` if a clear winner exists, add entries with `endpoint`, `best_for`, `unit_price_per_second_usd`.
4. Update `last_updated` to today.
5. Show diff before writing.

## Rules of thumb

- **Don't drift from user intent.** Refining a prompt is not rewriting the vision.
- **One generation per request.** Don't preemptively generate variants.
- **Aspect ratio for video.** Kling uses `aspect_ratio` ("16:9", "9:16", "1:1") passed directly. Change it via `default_args` in models.json if needed.
