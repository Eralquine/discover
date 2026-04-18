import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const progress = interpolate(frame, [0, durationInFrames - 1], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0f0f0f",
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
        gap: 24,
      }}
    >
      <div
        style={{
          width: 640,
          height: 16,
          borderRadius: 8,
          backgroundColor: "#2a2a2a",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${progress}%`,
            borderRadius: 8,
            background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
            transition: "width 0s",
          }}
        />
      </div>

      <span
        style={{
          color: "#ffffff",
          fontSize: 32,
          fontFamily: "monospace",
          fontWeight: 700,
          letterSpacing: 2,
        }}
      >
        {Math.round(progress)}%
      </span>
    </AbsoluteFill>
  );
};
