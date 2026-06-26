export const actionDE = "Spracheingabe" as const;
export const verbEN = "speak" as const;
export const productCategoryEN = "voice-input tool" as const;
export const outputArtifactEN = "transcript" as const;

export const antiVocabulary: readonly AntiVocabularyEntry[] = [
  {
    term: "Diktieren",
    replacement: actionDE,
  },
  {
    term: "dictate",
    replacement: verbEN,
  },
  {
    term: "dictation",
    replacement: productCategoryEN,
  },
  {
    term: "Diktat",
    replacement: "Transkript",
  },
  {
    term: "Voice assistant",
    replacement: "",
  },
  {
    term: "dictations",
    replacement: `${outputArtifactEN}s`,
  },
];
