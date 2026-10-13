import { useState, type FormEvent } from "react";
import { t, tMessage, type Message } from "./i18n";
import { navigate } from "./router";
import { Shell } from "./Shell";
import { uploadWork } from "./works";

/** Upload a Source. Reading it is a job; the Work page shows how it went, and why if it failed. */
export function Import() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Message | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const work = await uploadWork(file);
      navigate(`/works/${work.id}`);
    } catch (reason) {
      setError(reason as Message);
      setBusy(false);
    }
  };

  return (
    <Shell>
      <h1>{t("import.title")}</h1>
      <p className="muted">{t("import.intro")}</p>
      <form className="import" onSubmit={submit}>
        <input
          type="file"
          accept=".epub,.txt,application/epub+zip,text/plain"
          aria-label={t("import.choose")}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={!file || busy}>
          {busy ? t("import.uploading") : t("import.start")}
        </button>
      </form>
      {error && <p className="error">{tMessage(error)}</p>}
    </Shell>
  );
}
