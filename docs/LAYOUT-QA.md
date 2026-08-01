# Brand layout QA v2.1

The generator validates every build against explicit safe areas.

Checks include:

- text bounding boxes remain inside each platform-safe region;
- GitHub hero typography clears the lower frame;
- project subtitles remain readable in two-column profile cards;
- LinkedIn personal content clears the avatar overlap area;
- LinkedIn business content clears the Page-logo overlap area;
- every exported banner has the expected dimensions;
- rectangular social banners have no white or transparent corners.

Run:

```bash
./brandctl qa
```

The detailed machine-readable report is generated at:

```text
assets/generated/QA-REPORT.json
```
