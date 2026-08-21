export function clientLanguage() {
  if (typeof document === "undefined") return "ru";
  return document.cookie.match(/(?:^|; )anicast_lang=([^;]+)/)?.[1] === "en" ? "en" : "ru";
}

export function clientMessage(russian: string, english: string) {
  return clientLanguage() === "en" ? english : russian;
}
