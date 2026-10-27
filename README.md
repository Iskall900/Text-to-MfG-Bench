# Text-to-MfG Bench
Strucutre-aware Text-to-CAD Benchmark v1

## Keeping API keys out of git

Run once per clone so commits are checked for API keys:

```sh
git config core.hooksPath .githooks
```

The hook blocks staged changes containing the value of any exported `*KEY*`,
`*TOKEN*`, or `*SECRET*` variable, any value in `~/.config/text-to-mfg/keys.env`,
a DeepSeek-style `sk-` key, or a long literal assigned to a key/token/secret name.
Also enable GitHub secret scanning push protection in the repository settings.
See `Docker contents/README.md` for passing keys to containers.
