export function createTranslator(dictionary: Record<string, string>) {
  return (key: string, values: Record<string, string | number> = {}) => {
    const template = dictionary[key] ?? key;
    return Object.entries(values).reduce((message, [name, value]) => message.replaceAll(`{${name}}`, String(value)), template);
  };
}
