package org.fakester.common.component.display;

import com.inductiveautomation.ignition.common.jsonschema.JsonSchema;
import com.inductiveautomation.perspective.common.api.ComponentDescriptor;
import com.inductiveautomation.perspective.common.api.ComponentDescriptorImpl;
import org.fakester.common.Rag;

/**
 * Describes the RagChat component so the gateway and designer know to look for the front-end elements.
 */
public class RagChat {

    public static String COMPONENT_ID = "rad.display.ragChat";

    public static JsonSchema SCHEMA =
        JsonSchema.parse(Rag.class.getResourceAsStream("/ragchat.props.json"));

    public static ComponentDescriptor DESCRIPTOR = ComponentDescriptorImpl.ComponentBuilder.newBuilder()
        .setPaletteCategory(Rag.COMPONENT_CATEGORY)
        .setId(COMPONENT_ID)
        .setModuleId(Rag.MODULE_ID)
        .setSchema(SCHEMA)
        .setName("RAG Chat")
        .addPaletteEntry(
            "",
            "RAG Chat",
            "Ignition RAG/OPC/SQL assistant chat panel.",
            null,
            null
        )
        .setDefaultMetaName("ragChat")
        .setResources(Rag.BROWSER_RESOURCES)
        .build();
}
