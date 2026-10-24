"""
教务网页导入：正方旧版 / 强智 / 正方新版网页与 JSON / MHTML / GBK 编码 / 书签小工具拼接内容。
夹具按各系统真实页面结构精简而来。
"""

import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from types import SimpleNamespace

import pytest
from conftest import body

from app.core.errors import ApiError
from app.services.import_web import FRAME_MARKER, parse_web_timetable

USER = SimpleNamespace(total_weeks=20, period_times=None)

# 正方旧版 xskbcx.aspx：#Table1，课程块用 <br> 分隔，"上午/第1节" 在行首，合并单元格表示连上两节
ZF_OLD = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=gb2312">
<script>document.write('<table><tr><td>星期一</td><td>星期二</td><td>星期三</td></tr><tr><td>假课程<br>周一第1节{第1-2周}</td></tr></table>')</script>
</head><body>
<span id="lbl_xnxq">2025-2026学年第1学期 学生个人课表</span>
<table id="Table1" class="blacktab">
<tr><td colspan="2" rowspan="1">时间</td><td>星期一</td><td>星期二</td><td>星期三</td><td>星期四</td><td>星期五</td><td>星期六</td><td>星期日</td></tr>
<tr><td rowspan="4">上午</td><td>第1节</td>
  <td rowspan="2">高等数学A<br>周一第1,2节{第1-16周}<br>王老师<br>A101<br><br>线性代数<br>周一第1,2节{第17-18周}<br>陈老师<br>A102</td>
  <td>&nbsp;</td>
  <td rowspan="2">大学英语<br>周三第1,2节{第2-16周|双周}<br>李老师<br>B201</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>第2节</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>第3节</td><td>&nbsp;</td>
  <td rowspan="2">C++程序设计<br>周二第3,4节{第1-8周}<br>郭老师<br>机房305</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>体育(板块)</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>第4节</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table>
<select name="xnd"><option value="2024-2025">2024-2025</option><option selected="selected" value="2025-2026">2025-2026</option></select>
</body></html>"""

# 强智 xskb_list.do：#kbtable，div.kbcontent 是完整信息（kbcontent1 是精简版，应忽略），多门课用 ---- 分隔
QZ = """<html><body>
<table id="kbtable" class="Nsb_r_list Nsb_table">
<tr><th>&nbsp;</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th></tr>
<tr><th>第一大节<br>(01,02小节)<br>08:00-09:40</th>
  <td><input type="hidden" name="jx0415zbdiv_1" value="x"/>
    <div class="kbcontent1">数据结构<br/><font title='周次(节次)'>1-16(周)</font></div>
    <div class="kbcontent" style="display:none;">数据结构<br/><font title='老师'>张老师</font><br/><font title='周次(节次)'>1-16(周)[01-02节]</font><br/><font title='教室'>教1-101</font><br/>---------------------<br>离散数学<br/><font title='老师'>刘老师</font><br/><font title='周次(节次)'>1-8,10-16(周)[01-02节]</font><br/><font title='教室'>教1-102</font><br/></div>
  </td>
  <td><div class="kbcontent">&nbsp;</div></td>
  <td><div class="kbcontent">大学物理<br/><font title='老师'>赵老师</font><br/><font title='周次(节次)'>2-16(双周)</font><br/><font title='教室'>理科楼201</font><br/></div></td>
  <td><div class="kbcontent">&nbsp;</div></td><td><div class="kbcontent">&nbsp;</div></td></tr>
<tr><th>第二大节<br>(03,04小节)</th>
  <td><div class="kbcontent">&nbsp;</div></td>
  <td><div class="kbcontent">概率论<br/><font title='老师'>孙老师,周老师,吴老师,郑老师</font><br/><font title='周次(节次)'>1-12(周)[03-04节]</font><br/><font title='教室'>未排地点</font><br/></div></td>
  <td><div class="kbcontent">&nbsp;</div></td><td><div class="kbcontent">&nbsp;</div></td><td><div class="kbcontent">&nbsp;</div></td></tr>
</table></body></html>"""

# 正方新版 kbcx/xskbcx_cxXskbcxIndex.html 渲染后的 DOM：#kbgrid_table_0，td#{星期}-{节次}，div.timetable_con
ZF_NEW = """<html><body>
<table id="kbgrid_table_0" class="table timetable">
<tr><td></td><td></td><td><span class="index">星期一</span></td><td><span class="index">星期二</span></td><td><span class="index">星期三</span></td></tr>
<tr><td rowspan="4"><span class="time">上午</span></td><td><span class="festival">1</span></td>
  <td id="1-1" rowspan="2"><div class="timetable_con text-left"><span class="title"><font style="color:#0000ff">数据库原理★</font></span>
    <p><span class="glyphicon glyphicon-calendar" title="节/周"></span><font>(1-2节)1-16周(单)</font></p>
    <p><span class="glyphicon glyphicon-map-marker" title="上课地点"></span><font>教3-301</font></p>
    <p><span class="glyphicon glyphicon-user" title="教师 "></span><font>黄老师</font></p>
    <p><span class="glyphicon glyphicon-home" title="教学班名称"></span><font>(2025-2026-1)-数据库-01</font></p></div>
   <div class="timetable_con text-left"><span class="title"><font>软件工程◆</font></span>
    <p><span title="节/周"></span><font>(1-2节)2-16周(双)</font></p>
    <p><span title="上课地点"></span><font>教3-302</font></p>
    <p><span title="教师"></span><font>林老师</font></p></div></td>
  <td></td><td></td></tr>
<tr><td><span class="festival">2</span></td><td></td><td></td></tr>
<tr><td><span class="festival">3</span></td><td></td><td></td>
  <td id="3-3" rowspan="2"><div class="timetable_con"><span class="title"><font>操作系统</font></span>
    <p><span title="节/周"></span><font>(3-4节)1-18周</font></p>
    <p><span title="上课地点"></span><font>实验楼B</font></p>
    <p><span title="教师"></span><font>钱老师</font></p></div></td></tr>
<tr><td><span class="festival">4</span></td><td></td><td></td></tr>
<tr><td colspan="5">注：本学期2025-09-08正式上课，共18周</td></tr>
</table></body></html>"""

ZF_JSON = {
    "xsxx": {"XNMC": "2025-2026", "XQMMC": "2", "XM": "测试同学"},
    "kbList": [
        {"kcmc": "计算机网络", "xm": "何老师", "cdmc": "教2-201", "xqj": "1", "jcs": "1-2", "zcd": "1-16周"},
        {"kcmc": "编译原理", "xm": "冯老师,韩老师", "cdmc": "教2-202", "xqj": "4", "jcs": "5-6",
         "zcd": "1-8周(单),10-16周"},
        {"kcmc": "形势与政策", "xm": "", "cdmc": "", "xqj": "5", "jcs": "9-10", "zcd": "9-12周"},
        {"kcmc": "坏数据", "xqj": "", "jcs": "", "zcd": "1-16周"},
    ],
    "sjkList": [{"sjkcgs": "毕业实习 / 1-4周"}],
}


def by_name(result, name):
    return [c for c in result.courses if c["course_name"] == name]


# ---------------------------------------------------------------- 解析器
def test_zhengfang_old_table1_gb2312():
    result = parse_web_timetable("课表.html", ZF_OLD.encode("gb18030"), USER)
    assert result.format == "web" and result.semester == "2025-2026-1"
    names = {c["course_name"] for c in result.courses}
    assert names == {"高等数学A", "线性代数", "大学英语", "C++程序设计"}  # 脚本里的"假课程"不会被解析
    math = by_name(result, "高等数学A")[0]
    assert (math["day_of_week"], math["start_period"], math["end_period"]) == (1, 1, 2)
    assert math["weeks"] == list(range(1, 17)) and math["teacher"] == "王老师" and math["classroom"] == "A101"
    assert by_name(result, "线性代数")[0]["weeks"] == [17, 18]
    english = by_name(result, "大学英语")[0]
    assert english["day_of_week"] == 3 and english["weeks"] == list(range(2, 17, 2))
    cpp = by_name(result, "C++程序设计")[0]
    assert (cpp["day_of_week"], cpp["start_period"], cpp["end_period"], cpp["classroom"]) == (2, 3, 4, "机房305")
    assert any(s["name"] == "体育(板块)" for s in result.skipped)


def test_qiangzhi_kbcontent():
    result = parse_web_timetable("xskb.htm", QZ.encode("utf-8"), USER)
    assert len(result.courses) == 4  # kbcontent1 的精简副本不重复计入
    ds = by_name(result, "数据结构")[0]
    assert (ds["day_of_week"], ds["start_period"], ds["end_period"]) == (1, 1, 2)
    assert ds["teacher"] == "张老师" and ds["classroom"] == "教1-101" and ds["weeks"] == list(range(1, 17))
    lisan = by_name(result, "离散数学")[0]
    assert lisan["weeks"] == [*range(1, 9), *range(10, 17)] and lisan["classroom"] == "教1-102"
    # 周次里没写节次：用行首 "(01,02小节)"
    physics = by_name(result, "大学物理")[0]
    assert (physics["day_of_week"], physics["start_period"], physics["end_period"]) == (3, 1, 2)
    assert physics["weeks"] == list(range(2, 17, 2))
    prob = by_name(result, "概率论")[0]
    assert prob["teacher"] == "孙老师、周老师、吴老师等" and prob["classroom"] == "待定"
    assert (prob["day_of_week"], prob["start_period"]) == (2, 3)


def test_zhengfang_new_rendered_grid():
    result = parse_web_timetable("kb.html", ZF_NEW.encode("utf-8"), USER)
    db = by_name(result, "数据库原理")[0]
    assert (db["day_of_week"], db["start_period"], db["end_period"]) == (1, 1, 2)
    assert db["weeks"] == list(range(1, 17, 2)) and db["classroom"] == "教3-301" and db["teacher"] == "黄老师"
    se = by_name(result, "软件工程")[0]
    assert se["weeks"] == list(range(2, 17, 2)) and se["classroom"] == "教3-302" and se["teacher"] == "林老师"
    os_ = by_name(result, "操作系统")[0]
    assert (os_["day_of_week"], os_["start_period"], os_["end_period"]) == (3, 3, 4)
    # 页脚的开学日期与总周数；跨列的页脚不会被当成课程
    assert result.semester_start == "2025-09-08" and result.total_weeks == 18
    assert result.skipped == []


def test_total_weeks_widened_when_courses_exceed_setting():
    short = SimpleNamespace(total_weeks=16, period_times=None)
    result = parse_web_timetable("kb.html", ZF_OLD.encode("gb18030"), short)
    assert result.total_weeks == 18  # 线性代数 17-18 周
    assert parse_web_timetable("kb.html", QZ.encode(), short).total_weeks is None


def test_zhengfang_json_kblist():
    result = parse_web_timetable("pasted.json", json.dumps({"data": ZF_JSON}, ensure_ascii=False).encode(), USER)
    assert result.format == "zf-json" and result.semester == "2025-2026-2"
    assert [c["course_name"] for c in result.courses] == ["计算机网络", "编译原理", "形势与政策"]
    compiler = result.courses[1]
    assert compiler["weeks"] == [1, 3, 5, 7, *range(10, 17)] and compiler["teacher"] == "冯老师、韩老师"
    assert (compiler["day_of_week"], compiler["start_period"], compiler["end_period"]) == (4, 5, 6)
    reasons = {s["name"]: s["reason"] for s in result.skipped}
    assert "坏数据" in reasons and any("毕业实习" in name for name in reasons)


def test_mhtml_with_iframe_and_bookmarklet_frames():
    # Chrome "网页，单个文件"：外层页面只有 iframe，课表在另一个 text/html 部分里
    archive = MIMEMultipart("related")
    archive["MIME-Version"] = "1.0"
    archive.attach(MIMEText('<html><body><iframe src="xskb.do"></iframe></body></html>', "html", "utf-8"))
    archive.attach(MIMEText(QZ, "html", "utf-8"))
    result = parse_web_timetable("课表.mhtml", archive.as_bytes(), USER)
    assert len(result.courses) == 4

    # 书签小工具：顶层页面 + 同源 iframe 用标记拼接
    joined = "<html><body>导航</body></html>" + FRAME_MARKER + ZF_NEW
    assert len(parse_web_timetable("pasted.html", joined.encode(), USER).courses) == 3


@pytest.mark.parametrize(
    "content, message",
    [
        (b'<html><body><form><input type="password" name="pwd"></form></body></html>', "登录页面"),
        (b'<html><frameset><frame src="main.aspx"></frameset></html>', "内嵌框架"),
        (b"<html><body><table><tr><td>\xe6\x88\x90\xe7\xbb\xa9</td></tr></table></body></html>", "没有在网页里找到课表"),
        (b"just some words", "不是网页源代码"),
        (b'{"foo": 1}', "kbList"),
    ],
)
def test_helpful_errors(content, message):
    with pytest.raises(ApiError) as error:
        parse_web_timetable("pasted.html", content, USER)
    assert message in error.value.message


def test_empty_grid_and_bad_suffix():
    empty = "<table><tr><td></td><td>星期一</td><td>星期二</td><td>星期三</td></tr><tr><td>1</td><td></td><td></td><td></td></tr></table>"
    with pytest.raises(ApiError, match="查询"):
        parse_web_timetable("kb.html", empty.encode(), USER)
    with pytest.raises(ApiError) as error:
        parse_web_timetable("kb.exe", b"<html>", USER)
    assert error.value.status_code == 415


# ---------------------------------------------------------------- 接口
def _web(client, headers, content, name="pasted.html", mode="preview", selected=None):
    data = {"selected": selected} if selected is not None else None
    return client.post(f"/import/timetable/web?mode={mode}", headers=headers, files={"file": (name, content)}, data=data)


def test_web_import_preview_and_commit(client, register):
    alice, _ = register()
    bob, _ = register()
    preview = body(_web(client, alice, ZF_OLD.encode("gb18030"), "课表.html"))
    assert preview["format"] == "web" and preview["semester"] == "2025-2026-1" and preview["success_count"] == 4
    assert preview["courses"][0]["start_time"] == "08:00" and preview["courses"][0]["color"].startswith("#")
    assert body(client.get("/timetable", headers=alice))["courses"] == []

    keep = [i for i, c in enumerate(preview["courses"]) if c["course_name"] != "线性代数"]
    committed = body(_web(client, alice, ZF_OLD.encode("gb18030"), "课表.html", "commit", ",".join(map(str, keep))))
    assert committed["success_count"] == 3 and "reward" in committed
    table = body(client.get("/timetable", headers=alice))
    assert table["semester"] == "2025-2026-1" and len(table["courses"]) == 3
    # 别人的课表不受影响
    assert body(client.get("/timetable", headers=bob))["courses"] == []

    body(_web(client, alice, ZF_OLD.encode(), "课表.html", "commit", "99"), 422)
    body(_web(client, alice, b"<html>" + b" " * (5 * 1024 * 1024 + 1)), 413)
    assert client.post("/import/timetable/web", files={"file": ("a.html", b"<html>")}).status_code == 401


def test_excel_import_still_rejects_web_files(client, auth):
    response = client.post("/import/timetable?mode=preview", headers=auth, files={"file": ("课表.html", b"<html>")})
    body(response, 415)
