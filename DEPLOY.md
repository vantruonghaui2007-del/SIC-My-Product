# Đưa MIXVERSE lên mạng cho mọi người dùng thử

## Cách khuyên dùng: Hugging Face Spaces (miễn phí)

Dự án đã có sẵn `Dockerfile` chạy ở cổng 7860. Đây cũng là cổng mặc định của Hugging Face Spaces. Gói **CPU basic** miễn phí có 2 vCPU và 16 GB RAM, đủ cho engine nhạc local (numpy, scipy, librosa).

Hai lựa chọn khác **không** phù hợp:
- Vercel và Netlify không chạy được backend Python xử lý âm thanh.
- Các gói miễn phí 512 MB RAM dễ hết bộ nhớ khi render 3 phương án cùng lúc.

### Bước 1: Gộp code vào `master`

Gộp nhánh tính năng vào `master` (qua Pull Request trên GitHub). Workflow tự deploy chỉ chạy khi có push lên `master`.

### Bước 2: Tạo Space

1. Đăng ký tài khoản tại https://huggingface.co/join.
2. Mở https://huggingface.co/new-space và điền:
   - **Space name:** ví dụ `mixverse`
   - **SDK:** chọn **Docker**, sau đó chọn mẫu **Blank**
   - **Space hardware:** **CPU basic · Free**
   - **Visibility:** **Public**
3. Bấm **Create Space**.

Khối YAML ở đầu `README.md` chính là cấu hình của Space (`sdk: docker`, `app_port: 7860`), nên bạn không cần sửa gì thêm.

### Bước 3: Nối GitHub với Space để tự deploy

1. Tạo token trên Hugging Face: **Settings → Access Tokens → Create new token**, chọn loại **Write**, rồi sao chép token.
2. Trên GitHub, mở repo → **Settings → Secrets and variables → Actions**:
   - Tab **Secrets** → **New repository secret**: tên `HF_TOKEN`, giá trị là token vừa sao chép.
   - Tab **Variables** → **New repository variable**: tên `HF_SPACE`, giá trị `ten-cua-ban/mixverse`.
3. Mở tab **Actions** → **Deploy to Hugging Face Space** → **Run workflow**.

Từ giờ, mỗi lần push lên `master`, Space sẽ được cập nhật tự động.

4. Trên trang Space, mở tab **Logs** để xem quá trình build. Lần build đầu mất khoảng 5–10 phút.

Nếu không muốn dùng GitHub Actions, bạn có thể push tay. Khi được hỏi mật khẩu, hãy dán token Write:

```bash
git remote add space https://huggingface.co/spaces/ten-cua-ban/mixverse
```

```bash
git push --force space master:main
```

### Bước 4: Gửi link cho mọi người

Có hai dạng link:
- Trang Space: `https://huggingface.co/spaces/ten-cua-ban/mixverse`
- Link toàn màn hình, gọn hơn để chia sẻ: `https://ten-cua-ban-mixverse.hf.space`

## Lưu ý khi để web công khai

- **Bản demo công khai nên dùng engine local hoặc đặt `MIXVERSE_PROVIDER_ACCESS_TOKEN` riêng khi bật Google/ElevenLabs.** Khóa `GEMINI_API_KEY`/`ELEVENLABS_API_KEY` chỉ cấu hình ở backend. Người có mã truy cập AI có thể dùng hạn mức tính phí của bạn; xem [hướng dẫn Google](docs/GOOGLE_AI.md).
- **Space miễn phí sẽ ngủ** sau khoảng 48 giờ không có ai dùng. Người mở đầu tiên sau đó phải chờ khoảng 1 phút để Space khởi động lại.
- **Ổ đĩa của Space không lưu lâu dài.** File nhạc tự xoá sau 24 giờ và mất luôn khi Space khởi động lại, nên hãy nhắc người dùng tải về những bản họ thích.
- **Bạn có thể giảm dung lượng upload** cho bản demo: vào Space **Settings → Variables and secrets** và thêm biến `MIXVERSE_MAX_UPLOAD_MB` = `30`.
- **Máy chỉ có 2 vCPU,** mỗi lần sáng tác mất vài giây. Khi nhiều người bấm cùng lúc, họ sẽ phải chờ nhau. Nếu cần nhanh hơn, hãy nâng phần cứng trong Settings (tính phí).
- **Nội dung người dùng upload** ở Remix và Mashup phải tuân thủ quy định của Hugging Face. App đã bắt người dùng xác nhận có quyền sử dụng tệp.

## Cách nhanh để bạn bè thử ngay (không cần deploy)

Chạy app trên máy của bạn rồi mở một đường hầm Cloudflare. Cách này không cần tài khoản (cần cài [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)). Link chỉ hoạt động khi máy bạn đang bật.

```powershell
cd frontend; npm run build
```

```powershell
cd backend; $env:MIXVERSE_STATIC_DIR = "../frontend/dist"; python -m uvicorn mixverse.api:create_app_from_env --factory --port 8002
```

```powershell
cloudflared tunnel --url http://localhost:8002
```

Lệnh cuối sẽ in ra một link dạng `https://xxxx.trycloudflare.com`. Gửi link đó cho bạn bè là xong.

## Nơi khác

- **VPS có Docker:** build image rồi chạy lệnh dưới đây; web sẽ có ở cổng 80 của máy chủ.

  ```bash
  docker build -t mixverse .
  ```

  ```bash
  docker run -d -p 80:7860 -v mixverse-data:/data/mixverse --restart unless-stopped mixverse
  ```

- **Render, Railway, Fly.io:** đều dùng được `Dockerfile` này, nhưng nên chọn gói có từ 2 GB RAM trở lên.
