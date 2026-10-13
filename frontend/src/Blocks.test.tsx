import { render } from "@testing-library/react";
import { Blocks } from "./Blocks";

describe("Blocks", () => {
  it("renders marks, kinds and line breaks", () => {
    const { container } = render(
      <Blocks
        blocks={[
          { type: "heading", level: 2, spans: [{ text: "Chapter 1" }] },
          {
            type: "paragraph",
            spans: [
              { text: "“" },
              { text: "You", marks: ["italic"] },
              { text: " want", marks: ["bold", "italic"] },
            ],
          },
          { type: "section_break", spans: [] },
          { type: "quote", spans: [{ text: "Line one\nline two" }] },
        ]}
      />,
    );
    expect(container.querySelector(".block-heading")?.textContent).toBe("Chapter 1");
    expect(container.querySelector("p em")?.textContent).toBe("You");
    expect(container.querySelector("p em strong, p strong em")?.textContent).toBe(" want");
    expect(container.querySelector("hr.section-break")).toBeTruthy();
    expect(container.querySelectorAll("blockquote br")).toHaveLength(1);
  });
});
