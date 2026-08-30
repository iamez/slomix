/**
 * Source text helpers shared by the two ratchets (tokens.test.ts and
 * vocabulary.test.ts).
 *
 * A module rather than an export from one of the tests: importing a test file
 * to borrow a function RE-REGISTERS its suite, so the token tests ran twice
 * the moment the vocabulary ratchet reached for `stripJsComments`.
 */
/**
 * Every check below reads the stylesheet as CODE, never as prose. This file
 * is heavily commented — including comments that name tokens and quote the
 * `@theme static` line — and a guard that matches a comment is a guard that
 * a future paragraph can satisfy without a single declaration behind it
 * (the class that bit us in #798's source-matching guards). Stripping
 * comments once, here, is what keeps "declared" meaning declared.
 */
export function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '');
}

/**
 * The same rule for TS/TSX. It matters for exactly the reason the CSS one
 * does: a component that documents `var(--space-${step})` in a comment would
 * otherwise be recorded as READING a token named `--space-`, which nothing
 * declares — the guard would fail on prose while the code was correct, and
 * the tempting fix would be to reword the comment rather than to read code.
 *
 * Line comments are stripped only when the line begins with `//` or with a
 * `*` continuation, never mid-line: `'https://…'` inside a string must not
 * take the rest of its line with it.
 */
export function stripJsComments(text: string): string {
  return stripComments(text)
    .split('\n')
    .filter((line) => !/^\s*(\/\/|\*)/.test(line))
    .join('\n');
}

