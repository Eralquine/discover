import { Composition } from "remotion";
import { ProgressBar } from "./ProgressBar";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ProgressBar"
      component={ProgressBar}
      durationInFrames={90}
      fps={30}
      width={1280}
      height={720}
    />
  );
};
