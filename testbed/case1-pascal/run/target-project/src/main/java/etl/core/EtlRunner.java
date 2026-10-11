package etl.core;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import java.util.logging.Logger;

/**
 * Runs the registered jobs in dependency order.
 * Usage: java -cp ... etl.core.EtlRunner etl.properties [jobId ...]
 */
public final class EtlRunner {

    private static final Logger LOG = Logger.getLogger(EtlRunner.class.getName());

    private EtlRunner() {
    }

    /** Register jobs here, in dependency order. */
    static List<EtlJob> jobs(Properties p) {
        List<EtlJob> jobs = new ArrayList<EtlJob>();
        jobs.add(new etl.jobs.CustomerCleanJob(p.getProperty("notes.file")));
        jobs.add(new etl.jobs.OrderAmountJob());
        jobs.add(new etl.jobs.CitySummaryJob());
        return jobs;
    }

    public static void main(String[] args) throws IOException, SQLException {
        Properties p = new Properties();
        try (InputStream in = new FileInputStream(args.length > 0 ? args[0] : "etl.properties")) {
            p.load(in);
        }
        Tables.setSuffix(p.getProperty("table.suffix", "_NEW"));
        List<String> only = new ArrayList<String>();
        for (int i = 1; i < args.length; i++) {
            only.add(args[i]);
        }
        try (Connection conn = DriverManager.getConnection(
                p.getProperty("jdbc.url"), p.getProperty("jdbc.user"), p.getProperty("jdbc.password"))) {
            DataAccess da = new JdbcDataAccess(conn);
            for (EtlJob job : jobs(p)) {
                if (!only.isEmpty() && !only.contains(job.id())) {
                    continue;
                }
                LOG.info("running " + job.id());
                job.run(da);
            }
        }
    }
}
