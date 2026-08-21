"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getSessionUser } from "../lib/auth";

export function AccountLink() {
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    getSessionUser().then((user) => setAuthenticated(Boolean(user))).catch(() => undefined);
  }, []);

  return <Link className="profile" href={authenticated ? "/account" : "/login"}>{authenticated ? "Мой аккаунт" : "Войти"}</Link>;
}
