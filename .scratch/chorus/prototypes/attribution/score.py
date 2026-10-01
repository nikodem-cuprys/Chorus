"""PROTOTYPE, throwaway. Score each approach's Speakers against a reference labelling made by Claude from the
texts (not by the user). Where the text itself leaves a choice (a group speaking, a quoted phrase in first-person
narration), several answers are accepted. Run with any Python 3: python score.py"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).parent


def norm(s):
    return re.sub(r"^(the|a|an) ", "", re.sub(r"[^a-z ]", "", s.lower()).strip())




# Every way an approach may name each person. Key = reference name.
PEOPLE = {
    "01-pride-and-prejudice-ch1-2": {
        "Mr. Bennet": ["mr bennet", "her father", "their father", "his father"],
        "Mrs. Bennet": ["mrs bennet", "her mother", "his wife", "his lady", "their mother"],
        "Lizzy": ["lizzy", "elizabeth", "elizabeth bennet"], "Kitty": ["kitty"], "Lydia": ["lydia"]},
    "02-alice-mad-tea-party": {
        "Alice": ["alice"], "March Hare": ["march hare"], "Hatter": ["hatter", "mad hatter"], "Dormouse": ["dormouse"],
        "Group": ["three", "they", "other two"]},
    "03-holmes-scandal-in-bohemia": {
        "Holmes": ["sherlock holmes", "holmes"], "Watson": ["watson", "dr watson", "narrator character"]},
    "04-jane-eyre-ch1": {
        "Jane": ["jane", "jane eyre"], "Mrs. Reed": ["mrs reed"], "John": ["john reed", "john", "master reed"],
        "Eliza": ["eliza", "eliza reed"], "Bessie": ["bessie"], "Abbot": ["abbot"]},
    "05-metamorphosis-opening": {
        "Gregor": ["gregor samsa", "gregor"], "Mother": ["his mother", "gregors mother", "mother", "mrs samsa"],
        "Father": ["his father", "gregors father", "father", "mr samsa"],
        "Sister": ["his sister", "gregors sister", "sister", "grete"]},
    "06-crime-and-punishment-opening": {
        "Young man": ["young man", "raskolnikov"], "Drunken man": ["drunken man", "drunk man", "drunkard"]},
}
N = "Narrator"
# Reference: quote id -> accepted speakers (first is the main answer).
GOLD = {
    "01-pride-and-prejudice-ch1-2": {
        **{i: ["Mrs. Bennet"] for i in (2, 4, 6, 8, 10, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 38, 40, 46, 48, 52, 57,
                                        65, 67, 69, 72, 80, 84, 87, 89)},
        **{i: ["Mr. Bennet"] for i in (12, 15, 17, 19, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 45, 53, 55, 58, 60, 68, 70,
                                       73, 75, 77, 79, 82, 85)},
        **{i: ["Lizzy"] for i in (49, 51, 64)}, 61: ["Kitty"], 63: ["Kitty", "Mr. Bennet"], 90: ["Lydia"], 92: ["Lydia"]},
    "02-alice-mad-tea-party": {
        **{i: ["Alice"] for i in (1, 3, 7, 12, 16, 20, 22, 25, 27, 30, 32, 36, 40, 42, 58, 71, 73, 77, 79, 83, 91, 93, 99,
                                  101, 105, 110, 112, 119, 121, 125, 135, 147, 153, 158, 163, 168, 180, 188, 192, 194, 199,
                                  202, 204, 208, 213, 216, 221, 223, 227)},
        **{i: ["March Hare"] for i in (9, 14, 18, 34, 38, 46, 48, 63, 69, 96, 117, 165, 167, 178, 200)},
        **{i: ["Hatter"] for i in (23, 29, 43, 45, 52, 55, 59, 61, 65, 67, 74, 76, 80, 85, 89, 94, 102, 104, 107, 109, 113,
                                   115, 122, 124, 128, 130, 132, 137, 139, 144, 146, 149, 151, 155, 157, 160, 162, 182, 184,
                                   205, 207, 210, 231, 233)},
        **{i: ["Dormouse"] for i in (49, 51, 88, 142, 175, 177, 185, 187, 190, 195, 197, 215, 220, 224, 226, 229)},
        5: ["March Hare", "Hatter", "Dormouse", "Group"],
        **{i: ["March Hare", "Hatter", "Group"] for i in (170, 172, 218)}},
    "03-holmes-scandal-in-bohemia": {
        **{i: ["Holmes"] for i in (4, 6, 9, 11, 16, 18, 23, 25, 27, 29, 31, 33, 35, 43, 48, 50, 62, 65, 67)},
        **{i: ["Watson"] for i in (7, 10, 12, 14, 20, 22, 26, 28, 30, 40, 42, 45, 47, 64)},
        **{i: ["Watson", N] for i in (37, 39)},            # the note, read aloud by Watson
        **{i: [N, "Watson"] for i in (52, 54, 56, 58, 60)}},  # letters of the watermark, inside the narration
    "04-jane-eyre-ch1": {
        3: ["Mrs. Reed", N], 6: ["Mrs. Reed"], 66: ["Mrs. Reed"],
        **{i: ["Jane"] for i in (4, 27, 31, 48, 53, 55)},
        **{i: [N, "Jane"] for i in (10, 12, 14)}, 38: [N, "Jane", "Mrs. Reed"],  # quoted book text; a quoted phrase
        **{i: ["John"] for i in (22, 24, 26, 33, 35, 42, 44, 46, 49, 51, 57, 59, 61)},
        29: ["Eliza"], 63: ["Bessie", "Abbot"], 64: ["Bessie", "Abbot"]},
    "05-metamorphosis-opening": {
        **{i: ["Gregor"] for i in (1, 4, 6, 8, 11, 13, 15, 22, 32, 38, 40)},
        18: ["Mother"], 20: ["Mother"], 24: ["Father"], 26: ["Father"], 28: ["Father"], 30: ["Sister"], 34: ["Sister"]},
    "06-crime-and-punishment-opening": {
        **{i: ["Young man"] for i in (4, 6, 11, 13, 20, 22)}, 9: ["Drunken man"],
        15: [N, "Young man"], 17: [N, "Young man"]},  # scare-quoted words inside the narration
}


def person(stem, speaker):
    n = norm(speaker)
    if n in ("narrator", "unknown"):
        return speaker.capitalize()
    for ref, variants in PEOPLE[stem].items():
        if n in variants or n == norm(ref):
            return ref
    return f"?{speaker}"


if __name__ == "__main__":
    approaches = sorted(p.name for p in (ROOT / "scripts").iterdir() if p.is_dir())
    total = {a: [0, 0] for a in approaches}
    results = {}
    for stem, gold in GOLD.items():
        quotes = [l["id"] for l in json.loads((ROOT / "lines" / f"{stem}.json").read_text(encoding="utf-8"))["lines"]
                  if l["kind"] == "quote"]
        assert sorted(gold) == quotes, (stem, sorted(set(quotes) ^ set(gold)))
        row = []
        for a in approaches:
            s = json.loads((ROOT / "scripts" / a / f"{stem}.json").read_text(encoding="utf-8"))
            wrong = {}
            for i in quotes:
                lab = s["labels"].get(str(i))
                got = person(stem, lab["speaker"]) if lab else "(no label)"
                if got not in gold[i]:
                    wrong[i] = got
            total[a][0] += len(quotes) - len(wrong)
            total[a][1] += len(quotes)
            results.setdefault(stem, {})[a] = {"quotes": len(quotes), "wrong": wrong}
            row.append(f"{a}: {len(quotes) - len(wrong)}/{len(quotes)}")
        print(stem, "|", " | ".join(row))
        for a in approaches:
            w = results[stem][a]["wrong"]
            if w:
                print("   ", a, "wrong:", ", ".join(f"{i}={g} (ref {gold[i][0]})" for i, g in w.items()))
    print("TOTAL", {a: f"{c}/{n} = {100 * c / n:.1f}%" for a, (c, n) in total.items()})
    (ROOT / "score.json").write_text(json.dumps({"gold": {s: {str(i): v for i, v in g.items()} for s, g in GOLD.items()},
                                                 "results": results, "total": total}, indent=1), encoding="utf-8")
