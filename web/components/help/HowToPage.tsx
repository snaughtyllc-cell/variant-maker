import Link from "next/link";
import { CircleHelp } from "lucide-react";
import {
  HOW_TO_EYEBROW,
  HOW_TO_JUMP_LINKS,
  HOW_TO_LEAD,
  HOW_TO_SECTIONS,
  HOW_TO_TITLE,
} from "@/lib/howTo";

export function HowToPage() {
  return (
    <main className="how-to-page">
      <div className="workspace-heading">
        <span className="workspace-heading__icon">
          <CircleHelp size={19} />
        </span>
        <div>
          <p className="workspace-heading__eyebrow">{HOW_TO_EYEBROW}</p>
          <h1>{HOW_TO_TITLE}</h1>
          <p className="workspace-heading__copy">{HOW_TO_LEAD}</p>
        </div>
      </div>

      <article className="how-to-article">
        {HOW_TO_SECTIONS.map((section) => (
          <section key={section.id} className="how-to-section" aria-labelledby={`how-to-${section.id}`}>
            <h2 id={`how-to-${section.id}`}>{section.title}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            {section.bullets && section.bullets.length > 0 && (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </section>
        ))}

        <nav className="how-to-jumps" aria-label="Open a Studio tab">
          {HOW_TO_JUMP_LINKS.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </nav>
      </article>
    </main>
  );
}
