package org.fakester.gateway.endpoint;

import com.inductiveautomation.ignition.common.gson.JsonObject;
import com.inductiveautomation.ignition.gateway.dataroutes.RequestContext;
import com.inductiveautomation.ignition.gateway.dataroutes.RouteGroup;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import org.fakester.gateway.config.RagSettingsManager;

import javax.servlet.http.HttpServletResponse;

public final class RagEndpoints {

    private RagEndpoints() {
    }

    public static void mountRoutes(RouteGroup routes) {
        routes.newRoute("/rag/config")
            .type(RouteGroup.TYPE_JSON)
            .handler(RagEndpoints::getConfig)
            .mount();
    }

    private static JsonObject getConfig(RequestContext req, HttpServletResponse res) {
        GatewayContext context = req.getGatewayContext();
        return RagSettingsManager.getSettings(context).toJson();
    }

}
