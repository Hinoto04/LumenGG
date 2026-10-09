# LumenDB Play Store assets

Created with the built-in `image_gen` tool. The existing Lumen fractured-crystal
logo provided the identity reference; the app's charcoal/gold palette informed
both assets. Final PNG exports use the exact requested dimensions.

| File | Dimensions | PNG encoding | Size |
| --- | --- | --- | --- |
| `lumendb-icon-512.png` | 512 × 512 | 32-bit RGBA, opaque full-bleed background | 274,272 bytes |
| `lumendb-feature-1024x500.png` | 1024 × 500 | 24-bit RGB, no alpha | 922,752 bytes |

Dimensions, PNG color type, bit depth, icon alpha, file size and complete decoding
were verified. Both final exports were visually inspected. SHA-256 values are in
`manifest.json`. PNG exports were sized with Windows imaging; Python was used
only to inspect the final files.

The files follow the [Google Play preview asset specifications](https://support.google.com/googleplay/android-developer/answer/9866151).

Suggested feature graphic alt text:

> 검정·금색 배경의 LumenDB 이름과 카드·덱·컬렉션·QNA·계산기 기능 문구, 금색 카드와 HP·FP 계산기 그래픽.

## Icon generation prompt

Reference: `mobile/assets/icon.png`, the existing Lumen emblem.

```text
Use case: logo-brand. Asset type: Google Play store app icon for LumenDB. Create a polished square icon based on the supplied image 1, the existing Lumen fractured crystal emblem. Input image 1 is an identity reference: preserve the recognizable tall asymmetric diamond silhouette, its large diagonal split and separated polygon facets, with clean sharp edges, while simplifying tiny scratches that would disappear at icon size. Replace the white background with a solid near-black warm charcoal #171512. Render the crystal in warm gold #e0b45b, with subtle lighter gold facets and dark hairline geometric cuts. Flat premium graphic, crisply drawn, restrained shading, no photographic metallic reflections. The emblem is centered, occupies approximately 70 percent of the canvas height, with comfortable uniform breathing room for Play's adaptive rounded masking. Full-bleed square background, no pre-rounded corners, no outer frame, no drop shadow. Absolutely no text, initials, badge or watermark. Output a single finished icon, square, final target 512 x 512 pixels PNG. If using a larger generation canvas, keep exactly square with no border so it can be downsampled precisely. Background fully opaque.
```

## Feature graphic generation prompt

Reference: the newly generated gold/charcoal icon master, for palette and brand.

```text
Use case: ads-marketing. Asset type: Google Play feature graphic for the Korean LumenDB card database app. Generate one complete professionally art-directed panoramic banner, target canvas exactly 1024 x 500 pixels, approximately 2.048:1 aspect ratio. Input image 1 is a palette and brand reference only, not an edit target. Extend its warm gold fractured-crystal identity without repeating a large app icon. A premium clean graphic design in warm charcoal, deep bronze and luminous amber gold; soft restrained geometric lighting, a few broad polygon facets in the backdrop, subtle fine gold line accents. Typography and spacing should feel like a finished store campaign, not an infographic.
Composition: comfortably inset content with broad outer margins; important elements remain in the central area. Large beautifully typeset sans-serif app name on the left-center, exact text "LumenDB" with this capitalization. Immediately below, one concise Korean line, exact text "카드 검색부터 계산기까지". Below that, a smaller readable line, exact text "카드 · 덱 · 컬렉션 · QNA · 계산기". The right-center has a compact balanced composition of three overlapping elegant card-shaped panels with gold edge lines and abstract faceted crystal artwork, integrated with a small refined calculator-status panel reading exactly "HP 5000" and "FP 10". The card faces are stylized abstract graphics, no characters, no invented card rules or microtext. Avoid a large repeated logo; a tiny faceted accent near the brand title is sufficient. Flat graphic perspective with very subtle dimension, crisp editorial typography, controlled negative space. No phone or tablet body, no device frame, no store badge, no install button, no rankings, no watermark, no text beyond the three Korean/brand lines and the two HP/FP labels. Use the Korean text verbatim, clearly readable at final banner size. Opaque full-bleed background; square corners, no border. This is a single banner, not a sheet of variants. Preserve horizontal proportions close to 1024:500 even if generating at a higher resolution.
```
