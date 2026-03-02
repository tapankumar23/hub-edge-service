package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/segmentio/kafka-go"
	"gocv.io/x/gocv"
)

type CameraStatus struct {
	CameraID string    `json:"camera_id"`
	LastSeen time.Time `json:"last_seen"`
	Status   string    `json:"status"`
}

type FrameEvent struct {
	CameraID    string `json:"camera_id"`
	Timestamp   int64  `json:"timestamp"`
	ImageBase64 string `json:"image_base64"`
}

var (
	cameraURLs     []string
	cameraFPS      int
	statusMap      sync.Map
	ingestedFrames = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "ingested_frames_total",
			Help: "Total number of ingested frames",
		},
		[]string{"camera_id", "source"},
	)
)

func main() {
	prometheus.MustRegister(ingestedFrames)
	cameraURLs = strings.Split(os.Getenv("CAMERA_URLS"), ",")
	if len(cameraURLs) == 1 && cameraURLs[0] == "" {
		cameraURLs = []string{}
	}
	cameraFPS = 3
	if v := os.Getenv("CAMERA_FPS"); v != "" {
		if parsed, err := time.ParseDuration(v + "s"); err == nil {
			cameraFPS = int(parsed.Seconds())
		}
	}

	writer := kafka.NewWriter(kafka.WriterConfig{
		Brokers:  strings.Split(os.Getenv("KAFKA_BROKERS"), ","),
		Topic:    "frames",
		Balancer: &kafka.LeastBytes{},
	})

	for i, url := range cameraURLs {
		cameraID := "cam-" + string(rune('A'+i))
		go captureLoop(cameraID, url, writer)
	}

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		w.Write([]byte("ok"))
	})
	http.HandleFunc("/cameras", func(w http.ResponseWriter, r *http.Request) {
		var statuses []CameraStatus
		statusMap.Range(func(key, value interface{}) bool {
			statuses = append(statuses, value.(CameraStatus))
			return true
		})
		b, _ := json.Marshal(statuses)
		w.Header().Set("Content-Type", "application/json")
		w.Write(b)
	})
	http.HandleFunc("/cameras/refresh", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		w.Write([]byte("refreshed"))
	})
	http.HandleFunc("/ingest", func(w http.ResponseWriter, r *http.Request) {
		type In struct {
			CameraID    string `json:"camera_id"`
			ImageBase64 string `json:"image_base64"`
		}
		var in In
		if err := json.NewDecoder(r.Body).Decode(&in); err != nil || in.ImageBase64 == "" {
			http.Error(w, "invalid payload", http.StatusBadRequest)
			return
		}
		if in.CameraID == "" {
			in.CameraID = "api"
		}
		ingestedFrames.WithLabelValues(in.CameraID, "api").Inc()
		payload := FrameEvent{CameraID: in.CameraID, Timestamp: time.Now().UnixMilli(), ImageBase64: in.ImageBase64}
		b, _ := json.Marshal(payload)
		msg := kafka.Message{Value: b, Time: time.Now()}
		if err := writer.WriteMessages(context.Background(), msg); err != nil {
			http.Error(w, "publish failed", http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusAccepted)
		w.Write([]byte("queued"))
	})
	http.Handle("/metrics", promhttp.Handler())
	log.Fatal(http.ListenAndServe(":8081", nil))
}

func captureLoop(cameraID, url string, writer *kafka.Writer) {
	cap, err := gocv.OpenVideoCapture(url)
	if err != nil {
		statusMap.Store(cameraID, CameraStatus{CameraID: cameraID, LastSeen: time.Now(), Status: "error"})
		return
	}
	defer cap.Close()

	mat := gocv.NewMat()
	defer mat.Close()

	ticker := time.NewTicker(time.Second / time.Duration(cameraFPS))
	for range ticker.C {
		if ok := cap.Read(&mat); !ok || mat.Empty() {
			statusMap.Store(cameraID, CameraStatus{CameraID: cameraID, LastSeen: time.Now(), Status: "offline"})
			continue
		}
		buf, err := gocv.IMEncode(".jpg", mat)
		if err != nil {
			statusMap.Store(cameraID, CameraStatus{CameraID: cameraID, LastSeen: time.Now(), Status: "error"})
			continue
		}
		statusMap.Store(cameraID, CameraStatus{CameraID: cameraID, LastSeen: time.Now(), Status: "online"})
		ingestedFrames.WithLabelValues(cameraID, "rtsp").Inc()
		payload := FrameEvent{
			CameraID:    cameraID,
			Timestamp:   time.Now().UnixMilli(),
			ImageBase64: base64.StdEncoding.EncodeToString(buf.GetBytes()),
		}
		buf.Close()
		b, _ := json.Marshal(payload)
		msg := kafka.Message{Value: b, Time: time.Now()}
		writer.WriteMessages(context.Background(), msg)
	}
}
