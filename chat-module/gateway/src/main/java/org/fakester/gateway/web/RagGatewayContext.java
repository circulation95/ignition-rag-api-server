package org.fakester.gateway.web;

import com.inductiveautomation.ignition.gateway.model.GatewayContext;

public final class RagGatewayContext {
    private static volatile GatewayContext context;

    private RagGatewayContext() {
    }

    public static void set(GatewayContext gatewayContext) {
        context = gatewayContext;
    }

    public static GatewayContext get() {
        return context;
    }
}
