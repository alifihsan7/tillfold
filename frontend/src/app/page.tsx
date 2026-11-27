import LandingPage, { metadata as landingMetadata } from "./landing/LandingPage";
import { LandingEntry } from "./landing/LandingEntry";

export const metadata = landingMetadata;

export default function Home() {
  return (
    <>
      <LandingEntry />
      <LandingPage />
    </>
  );
}
