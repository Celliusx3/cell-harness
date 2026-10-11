"use client";

import type { ComponentType } from "react";

import { LocationRequest } from "@/components/answer/LocationRequest";
import { QuestionRequest } from "@/components/answer/QuestionRequest";
import { SecretRequest } from "@/components/answer/SecretRequest";
import type { ClientToolProps } from "@/components/answer/useClientTool";

/** The handler component for each client tool. */
export const CLIENT_TOOLS: Record<string, ComponentType<ClientToolProps>> = {
  ask_user: QuestionRequest,
  get_location: LocationRequest,
  ask_for_secret: SecretRequest,
};
