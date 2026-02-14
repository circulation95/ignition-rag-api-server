package org.fakester.gateway.config;

import com.inductiveautomation.ignition.gateway.localdb.persistence.IntField;
import com.inductiveautomation.ignition.gateway.localdb.persistence.PersistentRecord;
import com.inductiveautomation.ignition.gateway.localdb.persistence.RecordMeta;
import com.inductiveautomation.ignition.gateway.localdb.persistence.StringField;
import simpleorm.dataset.SFieldFlags;

public class RagSettingsRecord extends PersistentRecord {

    public static final RecordMeta<RagSettingsRecord> META =
        new RecordMeta<>(RagSettingsRecord.class, "RagSettings");

    public static final StringField Name =
        new StringField(META, "Name", SFieldFlags.SPRIMARY_KEY).setUnique(true).setDefault("default");

    public static final StringField ServerUrl =
        new StringField(META, "ServerUrl").setDefault("http://localhost");

    public static final IntField ServerPort =
        new IntField(META, "ServerPort").setDefault(8000);

    public static final StringField ChatPath =
        new StringField(META, "ChatPath").setDefault("/chat");

    public static final StringField DocUploadPath =
        new StringField(META, "DocUploadPath").setDefault("/documents/upload");

    public static final StringField DocListPath =
        new StringField(META, "DocListPath").setDefault("/documents/list");

    public static final StringField DocDeletePath =
        new StringField(META, "DocDeletePath").setDefault("/documents/delete");

    @Override
    public RecordMeta<?> getMeta() {
        return META;
    }
}
