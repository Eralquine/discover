---
name: remotion
description: Building video applications with Remotion, the React framework for programmatic video creation. Use when creating compositions, rendering videos, working with Remotion's animation APIs, or deploying video pipelines.
agents:
  - claude-code
---

# Remotion Skill

Build videos programmatically using React and Remotion. Remotion lets you write React components that render to video frames.

## Core Concepts

### Project Setup
```bash
# Create new project
npx create-video@latest

# Install in existing project
npm install remotion @remotion/cli
```

### Composition Structure
Every Remotion video is a composition — a React component with a fixed duration and fps:

```tsx
import { Composition } from "remotion";
import { MyVideo } from "./MyVideo";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MyVideo"
      component={MyVideo}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{ title: "Hello World" }}
    />
  );
};
```

### Animation APIs

```tsx
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

export const MyScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  // Linear interpolation
  const opacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Spring animation
  const scale = spring({
    frame,
    fps,
    config: { damping: 10, stiffness: 100, mass: 1 },
  });

  return (
    <div style={{ opacity, transform: `scale(${scale})` }}>
      Hello at frame {frame}
    </div>
  );
};
```

### Sequences and Timing

```tsx
import { Sequence, Audio, Video, Img } from "remotion";

export const Timeline: React.FC = () => (
  <AbsoluteFill>
    {/* Starts at frame 0, lasts 60 frames */}
    <Sequence from={0} durationInFrames={60}>
      <Intro />
    </Sequence>
    {/* Starts at frame 30 (overlaps with Intro) */}
    <Sequence from={30} durationInFrames={90}>
      <MainContent />
    </Sequence>
    {/* Audio track */}
    <Audio src={staticFile("audio.mp3")} startFrom={0} endAt={150} />
  </AbsoluteFill>
);
```

### Static Assets

```tsx
import { staticFile, Img, Video, Audio } from "remotion";

// Reference assets from public/ directory
<Img src={staticFile("logo.png")} />
<Video src={staticFile("clip.mp4")} />
<Audio src={staticFile("music.mp3")} />

// Remote URLs also work
<Img src="https://example.com/image.png" />
```

## Rendering

```bash
# Preview in browser (hot reload)
npx remotion studio

# Render to file
npx remotion render MyVideo output.mp4

# Render with custom props
npx remotion render MyVideo output.mp4 --props='{"title":"Custom Title"}'

# Render image sequence
npx remotion render MyVideo frames/ --image-format=png

# Render a single frame (for thumbnails)
npx remotion still MyVideo thumbnail.png --frame=30
```

## Lambda Rendering

```bash
# Install Lambda package
npm install @remotion/lambda

# Deploy functions and site
npx remotion lambda functions deploy
npx remotion lambda sites create --site-name=my-video

# Render in cloud
npx remotion lambda render <site-url> MyVideo out.mp4
```

```tsx
import { renderMediaOnLambda } from "@remotion/lambda/client";

const result = await renderMediaOnLambda({
  region: "us-east-1",
  functionName: "remotion-render-...",
  serveUrl: "https://...",
  composition: "MyVideo",
  inputProps: { title: "Hello" },
  codec: "h264",
});
```

## Common Patterns

### Text Animation
```tsx
const characters = "Hello".split("");
return (
  <>
    {characters.map((char, i) => {
      const delay = i * 3;
      const opacity = interpolate(frame, [delay, delay + 15], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      return <span key={i} style={{ opacity }}>{char}</span>;
    })}
  </>
);
```

### Loop / Ping-Pong
```tsx
import { loop, ping } from "@remotion/animation-utils";

// Loop animation every 60 frames
const loopedFrame = loop(frame, 60);

// Ping-pong between 0 and 1
const progress = interpolate(ping(frame, 60), [0, 1], [0, 1]);
```

### Off-thread Video
```tsx
import { OffthreadVideo } from "remotion";

// Use for better performance with video sources
<OffthreadVideo src={staticFile("video.mp4")} />
```

## Workflow

1. **Plan the composition**: Determine fps, duration (in frames = seconds × fps), and dimensions
2. **Build in Studio**: Run `npx remotion studio` for live preview while coding
3. **Test render**: Use `npx remotion render` or `npx remotion still` to verify output
4. **Optimize**: Use `<OffthreadVideo>`, `delayRender`/`continueRender` for async data
5. **Deploy**: Use `@remotion/lambda` for scalable cloud rendering

## Key Links
- Docs: https://www.remotion.dev/docs
- Player docs: https://www.remotion.dev/docs/player
- Lambda docs: https://www.remotion.dev/docs/lambda
