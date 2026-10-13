import { t, tMessage } from "./i18n";
import type { Voice } from "./voices";

/** A Voice's labels in the interface language: gender, age, accent and timbre words. */
export function voiceLabels(voice: Voice): string {
  const parts = [
    tMessage({ key: `voice.gender.${voice.gender}` }),
    tMessage({ key: `voice.age.${voice.age}` }),
    tMessage({ key: `voice.accent.${voice.accent}` }),
    ...voice.timbre.map((word) => tMessage({ key: `voice.timbre.${word}` })),
  ];
  return parts.join(" · ");
}

export function VoiceList({ voices }: { voices: Voice[] }) {
  if (voices.length === 0) {
    return <p className="muted">{t("voices.empty")}</p>;
  }
  return (
    <ul className="voices">
      {voices.map((voice) => (
        <li key={voice.id} className="voice">
          <div className="voice-head">
            <span className="voice-name">{voice.name}</span>
            {voice.default_narrator ? (
              <span className="tag">{t("voices.default_narrator")}</span>
            ) : (
              voice.narrator_ok && <span className="tag muted">{t("voices.narrator_ok")}</span>
            )}
          </div>
          <div className="small">{voiceLabels(voice)}</div>
          <audio controls preload="none" src={voice.clip_url} />
          {voice.credit && <div className="muted small">{voice.credit}</div>}
        </li>
      ))}
    </ul>
  );
}
