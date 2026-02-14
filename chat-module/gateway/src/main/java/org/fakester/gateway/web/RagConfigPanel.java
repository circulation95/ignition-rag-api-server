package org.fakester.gateway.web;

import com.inductiveautomation.ignition.common.gson.JsonObject;
import com.inductiveautomation.ignition.gateway.http.HttpClientManager;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.web.components.ConfigPanel;
import com.inductiveautomation.ignition.gateway.web.pages.IConfigPage;
import org.apache.http.HttpEntity;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.ContentType;
import org.apache.http.entity.StringEntity;
import org.apache.http.entity.mime.MultipartEntityBuilder;
import org.apache.http.util.EntityUtils;
import org.apache.wicket.markup.html.basic.Label;
import org.apache.wicket.markup.html.form.Button;
import org.apache.wicket.markup.html.form.Form;
import org.apache.wicket.markup.html.form.NumberTextField;
import org.apache.wicket.markup.html.form.TextField;
import org.apache.wicket.markup.html.form.upload.FileUpload;
import org.apache.wicket.markup.html.form.upload.FileUploadField;
import org.apache.wicket.model.Model;
import org.apache.wicket.model.PropertyModel;
import org.apache.wicket.util.lang.Bytes;
import org.apache.commons.lang3.tuple.Pair;
import org.fakester.gateway.config.RagSettings;
import org.fakester.gateway.config.RagSettingsManager;

import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.util.List;

public class RagConfigPanel extends ConfigPanel {

    private transient GatewayContext context;
    private final RagSettingsModel settingsModel;
    private final Model<String> statusModel;
    private final Model<String> docListModel;

    public RagConfigPanel(IConfigPage configPage) {
        super("ragConfig", configPage, null);
        this.context = RagGatewayContext.get();
        RagSettings settings = RagSettingsManager.getSettings(context);
        this.settingsModel = new RagSettingsModel(settings);
        this.statusModel = Model.of("");
        this.docListModel = Model.of("");

        addSettingsForm();
        addDocsForm();
        refreshDocList();
    }

    @Override
    public Pair<String, String> getMenuLocation() {
        return Pair.of("RAG", "settings");
    }

    public RagConfigPanel(String id, IConfigPage configPage, ConfigPanel returnPanel) {
        super(id, configPage, returnPanel);
        this.context = RagGatewayContext.get();
        RagSettings settings = RagSettingsManager.getSettings(context);
        this.settingsModel = new RagSettingsModel(settings);
        this.statusModel = Model.of("");
        this.docListModel = Model.of("");

        addSettingsForm();
        addDocsForm();
        refreshDocList();
    }

    private void addSettingsForm() {
        Form<Void> form = new Form<>("settingsForm") {
            @Override
            protected void onSubmit() {
                RagSettingsManager.saveSettings(context, settingsModel.toSettings());
                statusModel.setObject("Saved settings.");
            }
        };

        form.add(new TextField<>("serverUrl", new PropertyModel<>(settingsModel, "serverUrl")));
        form.add(new NumberTextField<>("serverPort", new PropertyModel<Integer>(settingsModel, "serverPort"), Integer.class));
        form.add(new TextField<>("chatPath", new PropertyModel<>(settingsModel, "chatPath")));
        form.add(new TextField<>("docUploadPath", new PropertyModel<>(settingsModel, "docUploadPath")));
        form.add(new TextField<>("docListPath", new PropertyModel<>(settingsModel, "docListPath")));
        form.add(new TextField<>("docDeletePath", new PropertyModel<>(settingsModel, "docDeletePath")));
        form.add(new Button("saveButton"));
        add(form);
    }

    private void addDocsForm() {
        Form<Void> docsForm = new Form<>("docsForm") {
            @Override
            protected void onSubmit() {
            }
        };
        docsForm.setMultiPart(true);
        docsForm.setMaxSize(Bytes.megabytes(50));

        FileUploadField uploadField = new FileUploadField("uploadFile");
        docsForm.add(uploadField);
        docsForm.add(new TextField<>("deleteName", new PropertyModel<>(settingsModel, "deleteName")));

        docsForm.add(new Button("uploadButton") {
            @Override
            public void onSubmit() {
                List<FileUpload> uploads = uploadField.getFileUploads();
                if (uploads == null || uploads.isEmpty()) {
                    statusModel.setObject("No file selected.");
                    return;
                }
                try {
                    FileUpload upload = uploads.get(0);
                    String url = settingsModel.buildUrl(settingsModel.docUploadPath);
                    HttpPost post = new HttpPost(url);
                    HttpEntity entity = MultipartEntityBuilder.create()
                        .addBinaryBody("file", upload.getBytes(), ContentType.DEFAULT_BINARY, upload.getClientFileName())
                        .build();
                    post.setEntity(entity);
                    String response = executeRequest(post);
                    statusModel.setObject("Upload: " + response);
                    refreshDocList();
                } catch (Exception ex) {
                    statusModel.setObject("Upload failed: " + ex.getMessage());
                }
            }
        });

        docsForm.add(new Button("deleteButton") {
            @Override
            public void onSubmit() {
                try {
                    if (settingsModel.deleteName == null || settingsModel.deleteName.isBlank()) {
                        statusModel.setObject("Enter a filename to delete.");
                        return;
                    }
                    String url = settingsModel.buildUrl(settingsModel.docDeletePath);
                    HttpPost post = new HttpPost(url);
                    JsonObject payload = new JsonObject();
                    payload.addProperty("name", settingsModel.deleteName);
                    post.setEntity(new StringEntity(payload.toString(), ContentType.APPLICATION_JSON));
                    String response = executeRequest(post);
                    statusModel.setObject("Delete: " + response);
                    refreshDocList();
                } catch (Exception ex) {
                    statusModel.setObject("Delete failed: " + ex.getMessage());
                }
            }
        });

        docsForm.add(new Button("refreshButton") {
            @Override
            public void onSubmit() {
                refreshDocList();
            }
        });

        docsForm.add(new Label("docList", docListModel));
        docsForm.add(new Label("statusMessage", statusModel));
        add(docsForm);
    }

    private void refreshDocList() {
        try {
            String url = settingsModel.buildUrl(settingsModel.docListPath);
            HttpGet get = new HttpGet(url);
            String response = executeRequest(get);
            docListModel.setObject(response);
        } catch (Exception ex) {
            docListModel.setObject("List failed: " + ex.getMessage());
        }
    }

    private String executeRequest(org.apache.http.client.methods.HttpUriRequest request) throws Exception {
        HttpClientManager manager = getContext().getHttpClientManager();
        HttpClient client = manager.getHttpClient();
        org.apache.http.HttpResponse response = client.execute(request);
        HttpEntity entity = response.getEntity();
        if (entity == null) {
            return "No response body.";
        }
        return EntityUtils.toString(entity, StandardCharsets.UTF_8);
    }

    private static class RagSettingsModel implements Serializable {
        private static final long serialVersionUID = 1L;
        public String serverUrl;
        public int serverPort;
        public String chatPath;
        public String docUploadPath;
        public String docListPath;
        public String docDeletePath;
        public String deleteName;

        private RagSettingsModel(RagSettings settings) {
            this.serverUrl = settings.serverUrl;
            this.serverPort = settings.serverPort;
            this.chatPath = settings.chatPath;
            this.docUploadPath = settings.docUploadPath;
            this.docListPath = settings.docListPath;
            this.docDeletePath = settings.docDeletePath;
            this.deleteName = "";
        }

        private RagSettings toSettings() {
            return new RagSettings(serverUrl, serverPort, chatPath, docUploadPath, docListPath, docDeletePath);
        }

        private String buildUrl(String path) {
            String base = serverUrl;
            if (!base.contains("://")) {
                base = "http://" + base;
            }
            String hostPart = base;
            int schemeIdx = base.indexOf("://");
            int hostStart = schemeIdx > -1 ? schemeIdx + 3 : 0;
            if (base.indexOf(":", hostStart) == -1 && serverPort > 0) {
                hostPart = base + ":" + serverPort;
            }
            String normalizedPath = path.startsWith("/") ? path : "/" + path;
            return hostPart + normalizedPath;
        }
    }

    private GatewayContext getContext() {
        if (context == null) {
            context = RagGatewayContext.get();
        }
        return context;
    }

}
