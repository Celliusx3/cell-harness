const LOCAL = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** An ISO instant in the viewer's own time zone and locale, date and time. */
export const localTime = (iso: string) => LOCAL.format(new Date(iso));
