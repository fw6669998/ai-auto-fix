package com.xxx.xxx;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ErrorReportUtil {

    private static final String ERROR_REPORT_URL = "http://192.168.1.100:3002/api/push/error";
    private static final String PROJECT_NAME = "xxx";

    public static class ErrorReport {
        public String error_message;
        public String error_content;
        public String project_name;
        public String hash_content;
    }

    public static class ErrorContent {
        public String exception;
        public String stack_trace;
        public String error_message;
        public List<RuntimeData> runtime_data = new ArrayList<>();
    }

    public static class RuntimeData {
        public String class_name;
        public String function_name;
        public Map<String, Object> param = new HashMap<>();
    }

    private final static Logger logger = LoggerFactory.getLogger(IUVLoggerUtil.class);

    private final static HttpClient HTTP_CLIENT = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private final static Gson GSON = new GsonBuilder().create();

    private static String toJson(Object obj) {
        return GSON.toJson(obj);
    }

    /**
     * 报告错误日志
     * 发送到指定http接口,不用等待响应,http可能开可能没开
     *
     * @param exp
     */
    public static void reportError(Exception exp, RuntimeData runtimeData) {
        try {
            ErrorContent errorContent = new ErrorContent();
            errorContent.exception = exp.getClass().getName();
            errorContent.error_message = exp.getMessage();
            StringWriter sw = new StringWriter();
            exp.printStackTrace(new PrintWriter(sw));
            String trace = sw.toString();
            errorContent.stack_trace = trace;
            if (runtimeData != null) {
                errorContent.runtime_data.add(runtimeData);
            }
            for (RuntimeData runtimeItem : errorContent.runtime_data) {
                for (String key : runtimeItem.param.keySet()) {
                    runtimeItem.param.put(key, String.valueOf(runtimeItem.param.get(key)));
                }
            }

            ErrorReport errorReport = new ErrorReport();
            errorReport.error_message = exp.getMessage();
            errorReport.error_content = toJson(errorContent);
            errorReport.project_name = PROJECT_NAME;
            errorReport.hash_content = trace;

            String json = toJson(errorReport);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(ERROR_REPORT_URL))
                    .timeout(Duration.ofSeconds(10))
                    .header("Content-Type", "application/json;charset=UTF-8")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
            HTTP_CLIENT.sendAsync(request, HttpResponse.BodyHandlers.discarding())
                    .exceptionally(throwable -> {
                        logger.info("报告错误异常: {}", throwable.getMessage());
                        return null;
                    });
            logger.info("报告错误");
        } catch (Exception e) {
            logger.info("报告错误失败: {}", e.getMessage());
        }
    }
}
