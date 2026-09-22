"use client";

import type { ComponentType } from "react";

import { LocationRequest } from "@/components/answer/LocationRequest";
import type { ClientToolProps } from "@/components/answer/useClientTool";

/** The handler component for each client tool. */
export const CLIENT_TOOLS: Record<string, ComponentType<ClientToolProps>> = {
  get_location: LocationRequest,
};
