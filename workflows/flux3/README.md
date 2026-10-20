# Pinned FLUX 3 workflow versions

`workflow-catalog.json` is the B3 source of truth for local image generation.
It pins the reference graph and identifies only the slots the orchestrator may
change. `flux3-stone-workflow.json` at the project root remains the original
read-only proof-of-concept graph and is never edited.

## `flux3-klein-v1`

| Item | Value |
| --- | --- |
| Reference | `../../flux3-stone-workflow.json` |
| Reference SHA-256 | `afb43e8e2238cc75613e33d0f68875a6a0af527ebc007efb6d3b4807eb73db0c` |
| UNET | `flux3_image_klein_sd_int8_convrot.safetensors` |
| Encoder | `qwen3vl_4b_int8_convrot.safetensors` (`type: flux3`) |
| VAE | `flux2-vae.safetensors` |
| Sampling | 16 steps, CFG 1.0, Euler, simple, denoise 1.0, batch 1 |
| Resolution | 16-pixel multiple, 16–4096 edge (profile budget may be tighter) |

Mutable slots:

| Node | Class | Inputs changed |
| --- | --- | --- |
| `4` | `CLIPTextEncode` | positive prompt text |
| `5` | `CLIPTextEncode` | negative prompt text |
| `6` | `EmptyFlux2LatentImage` | width, height, batch size |
| `7` | `KSampler` | seed, steps, cfg, sampler, scheduler, denoise |
| `9` | `SaveImage` | filename prefix (`b3-<request-id>`) |

Each run writes a complete parameterized copy to
`workflows/generated/<run>/workflow.json`; the original reference is only read
and its hash is checked before every run. Any change to the reference file is a
hard failure until the catalog is deliberately updated.

## Paid/partner nodes

The catalog allowlist contains only the eight core classes used by this graph.
The preflight also rejects any installed class reporting `api_node: true`.
ComfyUI's hosted FLUX/Seedream/Kling/etc. nodes are therefore not runnable through
this pipeline. No cloud endpoint, upload or paid generation is used.

## Negative prompts

The graph uses CFG 1.0. Negative text is submitted and recorded, but classifier-free
negative guidance is inactive, so it is not a reliable constraint. Put essential
visual requirements in the positive prompt and in B2 review criteria.

## Adding a version

Add a new catalog entry with a distinct version, pin its own reference hash,
model filenames and allowed classes, then validate it with B3 tests and a dry-run
before any authorized generation. Do not rewrite an existing version in place.
