package org.example;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
public class myStreamsApp {
    public static void main(String[] args) {
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "kafka-streams-app");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka1:19092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.String().getClass().getName());
        props.put(ProducerConfig.MAX_REQUEST_SIZE_CONFIG, 2097152); // 2 MB

        StreamsBuilder builder = new StreamsBuilder();
        KStream<String, String> stream = builder.stream("subway");
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
                .withZone(ZoneId.of("UTC"));

        // subwayId 변환 맵핑 정의
        Map<String, String> subwayIdMap = new HashMap<>();
        subwayIdMap.put("1001", "1호선");
        subwayIdMap.put("1002", "2호선");
        subwayIdMap.put("1003", "3호선");
        subwayIdMap.put("1004", "4호선");
        subwayIdMap.put("1005", "5호선");
        subwayIdMap.put("1006", "6호선");
        subwayIdMap.put("1007", "7호선");
        subwayIdMap.put("1008", "8호선");
        subwayIdMap.put("1009", "9호선");
        subwayIdMap.put("1063", "경의중앙선");
        subwayIdMap.put("1065", "공항철도");
        subwayIdMap.put("1067", "경춘선");
        subwayIdMap.put("1075", "수인분당선");
        subwayIdMap.put("1077", "신분당선");
        subwayIdMap.put("1092", "우이신설선");
        subwayIdMap.put("1032", "GTX-A");
        subwayIdMap.put("1081", "경강선");
        subwayIdMap.put("1093", "서해선");
        subwayIdMap.put("1094", "신림선");

        //데이터 변환 부분
        KStream<String, String> transformedStream = stream.mapValues(value -> {
            try {
                ObjectMapper objectMapper = new ObjectMapper();
                JsonNode rootNode = objectMapper.readTree(value);

                JsonNode arrivalListNode = rootNode.get("realtimeArrivalList");

                if (arrivalListNode.isArray()) {
                    for (JsonNode node : arrivalListNode) {
                        ((ObjectNode) node).remove("beginRow");
                        ((ObjectNode) node).remove("endRow");
                        ((ObjectNode) node).remove("curPage");
                        ((ObjectNode) node).remove("pageRow");
                        ((ObjectNode) node).remove("selectedCount");
                        ((ObjectNode) node).remove("subwayNm");
                        ((ObjectNode) node).remove("trainLineNm");
                        ((ObjectNode) node).remove("subwayHeading");
                        ((ObjectNode) node).remove("trainCo");
                        ((ObjectNode) node).remove("trnsitCo");
                        ((ObjectNode) node).remove("statnTid");
                        ((ObjectNode) node).remove("statnFid");
                        ((ObjectNode) node).remove("ordkey");
                        ((ObjectNode) node).remove("subwayList");
                        ((ObjectNode) node).remove("statnList");
                        ((ObjectNode) node).remove("btrainNo");
                        ((ObjectNode) node).remove("arvlMsg3");
                        ((ObjectNode) node).remove("arvlCd");
                        ((ObjectNode) node).remove("statnId");
                        ((ObjectNode) node).remove("bstatnId");
                        ((ObjectNode) node).remove("lstcarAt");

                        //역 이름: 괄호 제거 + 응암순환(상선) 인 경우 응암으로 변경
                        String statnNmValue = node.get("statnNm").asText();

                        if (statnNmValue.contains("(")) {
                            statnNmValue = statnNmValue.replaceAll("\\(.*\\)", "").trim();
                            ((ObjectNode) node).put("statnNm", statnNmValue);
                        }

                        // '응암순환'을 '응암'으로 변경
                        if ("응암순환".equals(statnNmValue)) {
                            ((ObjectNode) node).put("statnNm", "응암");
                        }


                        long recptnDtValue = node.get("recptnDt").asLong();
                        String formattedDate = formatter.format(Instant.ofEpochMilli(recptnDtValue));
                        ((ObjectNode) node).put("recptnDt", formattedDate);

                        // subwayId 변환
                        String subwayIdValue = node.get("subwayId").asText();
                        String transformedSubwayId = subwayIdMap.getOrDefault(subwayIdValue, subwayIdValue);
                        ((ObjectNode) node).put("subwayId", transformedSubwayId);

                        // barvlDt 변환 (초를 분초 형식으로 변환)
                        if (node.has("barvlDt")) {
                            int barvlDtSeconds = node.get("barvlDt").asInt();
                            int minutes = barvlDtSeconds / 60;
                            int seconds = barvlDtSeconds % 60;
                            String barvlDtFormatted = String.format("%d분 %d초", minutes, seconds);
                            ((ObjectNode) node).put("barvlDt", barvlDtFormatted);
                        }
                    }
                }

                ObjectNode wrapperNode = objectMapper.createObjectNode();
                wrapperNode.set("data", arrivalListNode);

                return objectMapper.writeValueAsString(wrapperNode);
            } catch (Exception e) {
                return "{\"error\":\"Error processing data\"}";
            }
        });

        transformedStream.to("output-topic", Produced.with(Serdes.String(), Serdes.String()));

        KafkaStreams streams = new KafkaStreams(builder.build(), props);
        streams.start();
    }
}
