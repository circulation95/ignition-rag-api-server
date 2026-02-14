package org.fakester.gateway.config;

import com.inductiveautomation.ignition.gateway.localdb.persistence.PersistenceInterface;
import com.inductiveautomation.ignition.gateway.localdb.persistence.RecordMeta;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import simpleorm.utils.SException;

public class RagSettingsManager {

    private RagSettingsManager() {
    }

    public static void ensureSchema(GatewayContext context) {
        try {
            context.getSchemaUpdater().updatePersistentRecords(RagSettingsRecord.META);
        } catch (Exception ignored) {
        }
    }

    public static RagSettings getSettings(GatewayContext context) {
        RagSettingsRecord record = getOrCreate(context);
        return new RagSettings(
            record.getString(RagSettingsRecord.ServerUrl),
            record.getIntObj(RagSettingsRecord.ServerPort) == null ? 0 : record.getIntObj(RagSettingsRecord.ServerPort),
            record.getString(RagSettingsRecord.ChatPath),
            record.getString(RagSettingsRecord.DocUploadPath),
            record.getString(RagSettingsRecord.DocListPath),
            record.getString(RagSettingsRecord.DocDeletePath)
        );
    }

    public static void saveSettings(GatewayContext context, RagSettings settings) {
        RagSettingsRecord record = getOrCreate(context);
        record.setString(RagSettingsRecord.ServerUrl, settings.serverUrl);
        record.setInt(RagSettingsRecord.ServerPort, settings.serverPort);
        record.setString(RagSettingsRecord.ChatPath, settings.chatPath);
        record.setString(RagSettingsRecord.DocUploadPath, settings.docUploadPath);
        record.setString(RagSettingsRecord.DocListPath, settings.docListPath);
        record.setString(RagSettingsRecord.DocDeletePath, settings.docDeletePath);
        try {
            context.getPersistenceInterface().save(record);
        } catch (SException ignored) {
        }
    }

    private static RagSettingsRecord getOrCreate(GatewayContext context) {
        PersistenceInterface persistence = context.getPersistenceInterface();
        RagSettingsRecord record = persistence.find(RagSettingsRecord.META, "default");
        if (record == null) {
            record = persistence.createNew(RagSettingsRecord.META);
            record.setString(RagSettingsRecord.Name, "default");
            record.installDefaultValues();
            try {
                persistence.save(record);
            } catch (SException ignored) {
            }
        }
        return record;
    }
}
