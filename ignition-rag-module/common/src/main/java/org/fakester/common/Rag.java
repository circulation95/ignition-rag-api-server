package org.fakester.common;

import java.util.Set;

import com.inductiveautomation.perspective.common.api.BrowserResource;

public class Rag {

    public static final String MODULE_ID = "org.fakester.ragcomponent";
    public static final String URL_ALIAS = "ragcomponents";
    public static final String COMPONENT_CATEGORY = "RAG";
    public static final Set<BrowserResource> BROWSER_RESOURCES =
        Set.of(
            new BrowserResource(
                "ragcomponents-js",
                String.format("/res/%s/RagComponents.js", URL_ALIAS),
                BrowserResource.ResourceType.JS
            ),
            new BrowserResource("ragcomponents-css",
                String.format("/res/%s/RagComponents.css", URL_ALIAS),
                BrowserResource.ResourceType.CSS
            )
        );
}
