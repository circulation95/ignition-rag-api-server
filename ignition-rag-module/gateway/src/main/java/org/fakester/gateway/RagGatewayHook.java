package org.fakester.gateway;

import java.util.List;
import java.util.Optional;

import com.inductiveautomation.ignition.common.BundleUtil;
import com.inductiveautomation.ignition.common.licensing.LicenseState;
import com.inductiveautomation.ignition.common.util.LoggerEx;
import com.inductiveautomation.ignition.gateway.dataroutes.RouteGroup;
import com.inductiveautomation.ignition.gateway.model.AbstractGatewayModuleHook;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.web.models.ConfigCategory;
import com.inductiveautomation.ignition.gateway.web.models.DefaultConfigTab;
import com.inductiveautomation.ignition.gateway.web.models.IConfigTab;
import com.inductiveautomation.perspective.common.api.ComponentRegistry;
import com.inductiveautomation.perspective.gateway.api.ComponentModelDelegateRegistry;
import com.inductiveautomation.perspective.gateway.api.PerspectiveContext;
import org.fakester.common.Rag;
import org.fakester.gateway.config.RagSettingsManager;
import org.fakester.gateway.web.RagConfigPanel;
import org.fakester.gateway.web.RagGatewayContext;

public class RagGatewayHook extends AbstractGatewayModuleHook {

    private static final LoggerEx log = LoggerEx.newBuilder().build("sn.gateway.RagComponents");
    private static final ConfigCategory RAG_CATEGORY = new ConfigCategory("RAG", "RAG.nav.header", 700);
    private static final IConfigTab RAG_CONFIG_ENTRY = DefaultConfigTab.builder()
        .category(RAG_CATEGORY)
        .name("settings")
        .i18n("RAG.nav.settings.title")
        .page(RagConfigPanel.class)
        .terms("rag settings fastapi")
        .build();

    private GatewayContext gatewayContext;
    private PerspectiveContext perspectiveContext;
    private ComponentRegistry componentRegistry;
    private ComponentModelDelegateRegistry modelDelegateRegistry;

    @Override
    public void setup(GatewayContext context) {
        this.gatewayContext = context;
        RagGatewayContext.set(context);
        RagSettingsManager.ensureSchema(context);
        BundleUtil.get().addBundle("RAG", getClass(), "rag");
        log.info("RAG Components.");
    }

    @Override
    public void startup(LicenseState activationState) {
        log.info("Starting up RAG Components Hook!");

        this.perspectiveContext = PerspectiveContext.get(this.gatewayContext);
        this.componentRegistry = this.perspectiveContext.getComponentRegistry();
        this.modelDelegateRegistry = this.perspectiveContext.getComponentModelDelegateRegistry();


        if (this.componentRegistry != null) {
            log.info("Registering components.");
            this.componentRegistry.registerComponent(org.fakester.common.component.display.RagChat.DESCRIPTOR);
        } else {
            log.error("Reference to component registry not found, components will fail to function!");
        }

        if (this.modelDelegateRegistry != null) {
            log.info("Registering model delegates.");
        } else {
            log.error("ModelDelegateRegistry was not found!");
        }

    }

    @Override
    public void shutdown() {
        log.info("Shutting down RAG module and removing registered components.");
        if (this.componentRegistry != null) {
            this.componentRegistry.removeComponent(org.fakester.common.component.display.RagChat.COMPONENT_ID);
        } else {
            log.warn("Component registry was null, could not unregister components.");
        }

    }

    @Override
    public Optional<String> getMountedResourceFolder() {
        return Optional.of("mounted");
    }

    @Override
    public void mountRouteHandlers(RouteGroup routeGroup) {
        org.fakester.gateway.endpoint.RagEndpoints.mountRoutes(routeGroup);
    }

    @Override
    public List<? extends IConfigTab> getConfigPanels() {
        return List.of(
            RAG_CONFIG_ENTRY
        );
    }

    @Override
    public List<ConfigCategory> getConfigCategories() {
        return List.of(RAG_CATEGORY);
    }

    // Lets us use the route http://<gateway>/res/rag/*
    @Override
    public Optional<String> getMountPathAlias() {
        return Optional.of(Rag.URL_ALIAS);
    }

    @Override
    public boolean isFreeModule() {
        return true;
    }
}
