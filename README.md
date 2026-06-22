# media-gen

Local image and video generation pipeline via [MuAPI](https://muapi.ai). Pay per generation, no subscription. 341 models: FLUX, Midjourney, GPT-image, Imagen4, Kling, Seedance, Veo3, Sora, WAN, and more.

## What it does

You describe media casually ("a photo of a dog swimming with a tennis ball"). Claude refines the prompt, picks the best model from `models.json`, generates via MuAPI, saves to a dated local folder, and offers to animate the image into video.

All artifacts (`prompt.md`, `image-NN.png`, `video-NN.mp4`) live in one folder per generation.

## Install

Drop the `media-gen` folder into your Claude Code skills directory:

- Mac/Linux: `~/.claude/skills/media-gen/`
- Windows: `C:\Users\<you>\.claude\skills\media-gen\`

Then:

1. **Get a MuAPI key.** Sign up at https://muapi.ai and copy your API key from the dashboard.

2. **Set the env var:**
   - Mac/Linux: add `export MUAPI_KEY="your-key-here"` to `~/.zshrc`, then `source ~/.zshrc`
   - Windows: `setx MUAPI_KEY "your-key-here"`, then restart terminal

3. **Install the dependency:**
   ```
   pip install requests
   ```

4. **Test it.** In any Claude Code session, say:
   > generate a photo of a single red apple on a white background

## Usage

Just talk to Claude:

- *"generate a photo of ..."*
- *"make me an image where ..."*
- *"create a video of ..."* (text-to-video)
- *"turn this image into a video"* (image-to-video)
- *"upscale this image"*

Claude reads `SKILL.md`, refines the prompt, picks the model, runs `scripts/generate.py`, saves to `~/Documents/Media Gen/<date>-<slug>/`.

## Model registry

`models.json` contains 341 models from the live MuAPI catalog, organized by category:

| Section | Count | Examples |
|---|---|---|
| `image` | 62 | flux-dev, midjourney-v8, nano-banana-pro, gpt4o, imagen4 |
| `image_edit` | 62 | flux-kontext-dev-i2i, nano-banana-edit, gpt4o-edit |
| `video` | 181 | kling-v3, seedance-2.5, veo3.1, wan2.7, sora-2, runway |
| `upscale` | 3 | ai-image-upscaler, topaz-image-upscale, seedvr2 |
| `audio_to_video` | 13 | latent-sync, kling-avatar, omnihuman |
| `image_to_3d` | 8 | tripo3d, meshy |
| `audio` | 12 | suno, mmaudio |

To refresh the catalog: `curl https://api.muapi.ai/api/v1/models` (no auth).

## Configuration

Edit `config.json` to change the output directory. Default: `~/Documents/Media Gen`.

## File structure

```
media-gen/
├── SKILL.md            # Workflow instructions Claude reads
├── README.md           # This file
├── config.json         # Output dir
├── models.json         # Full MuAPI model catalog (341 models)
└── scripts/
    └── generate.py     # CLI: image | video | upscale subcommands
```

## Troubleshooting

| Error | Fix |
|---|---|
| `MUAPI_KEY not set` | Add `export MUAPI_KEY="..."` to `~/.zshrc`, then `source ~/.zshrc` |
| `requests not installed` | `pip install requests` |
| HTTP 404 on endpoint | Endpoint slug changed. Fetch `https://api.muapi.ai/api/v1/models` for current slugs |
| Generation hangs | Images: under 30s. Videos: 1–3 min. If over 10 min, kill and retry |

## Cost (MuAPI, 2026)

- flux-dev: ~$0.015/image
- kling-v3.0-pro I2V 5s: ~$0.72/video
- veo3.1-fast T2V: ~$0.60/video
- seedance-pro I2V: ~$0.18/video

Current pricing always in `models.json` (`cost_usd` field) and live at `https://api.muapi.ai/api/v1/models`.
