package org.fakester.gateway.config;

import com.inductiveautomation.ignition.common.gson.JsonObject;

public class RagSettings {
    public final String serverUrl;
    public final int serverPort;
    public final String chatPath;
    public final String docUploadPath;
    public final String docListPath;
    public final String docDeletePath;

    public RagSettings(
        String serverUrl,
        int serverPort,
        String chatPath,
        String docUploadPath,
        String docListPath,
        String docDeletePath
    ) {
        this.serverUrl = serverUrl;
        this.serverPort = serverPort;
        this.chatPath = chatPath;
        this.docUploadPath = docUploadPath;
        this.docListPath = docListPath;
        this.docDeletePath = docDeletePath;
    }

    public JsonObject toJson() {
        JsonObject json = new JsonObject();
        json.addProperty("serverUrl", serverUrl);
        json.addProperty("serverPort", serverPort);
        json.addProperty("chatPath", chatPath);
        json.addProperty("docUploadPath", docUploadPath);
        json.addProperty("docListPath", docListPath);
        json.addProperty("docDeletePath", docDeletePath);
        return json;
    }
}
