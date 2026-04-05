import asyncio
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from app.config.settings import get_settings
from app.infra.postgres.database import init_database, get_session
from app.infra.postgres.models import User, Document, IngestionJob, ChatSession, ChatMessage
from app.infra.elasticsearch.client import ElasticsearchClient
from app.application.ingestion_service import IngestionService
from app.infra.langchain.embeddings import CustomOllamaEmbeddings

SAMPLE_DOCUMENTS = [
    {
        "filename": "四羊方尊.txt",
        "source": "青铜馆",
        "tags": ["青铜器", "商代"],
        "content": (
            "四羊方尊出土于湖南宁乡，铸造于商代晚期。"
            "器物将方形器体与立体羊首巧妙结合，展现了高超的青铜铸造水平。"
            "它不仅是祭祀礼器，也体现了古代社会的礼制与审美。"
            "四羊方尊是商代晚期青铜礼器，器身四角各铸一只卷角羊，纹饰繁复，工艺精湛。"
        ),
    },
    {
        "filename": "唐三彩骆驼载乐俑.txt",
        "source": "陶瓷馆",
        "tags": ["陶瓷", "唐代"],
        "content": (
            "唐三彩骆驼载乐俑常见于唐代高等级墓葬。"
            "骆驼昂首嘶鸣，驼峰间乐伎演奏起舞，呈现出盛唐开放多元的社会风貌。"
            "其釉色以黄、绿、白为主，具有鲜明的装饰性与叙事性。"
            "唐三彩骆驼载乐俑是唐代三彩明器，以骆驼驮载乐舞人物，生动反映丝绸之路文化交流。"
        ),
    },
    {
        "filename": "清明上河图.txt",
        "source": "书画馆",
        "tags": ["书画", "北宋"],
        "content": (
            "《清明上河图》传为北宋画家张择端所作。"
            "画卷以散点透视展开城市与郊野空间，细致描绘市井百态、商贸往来与舟车交通。"
            "它既是杰出的绘画作品，也是研究宋代社会生活的重要图像文献。"
            "清明上河图是北宋风俗长卷，描绘汴京及汴河沿岸繁华景象，具有重要史料与艺术价值。"
        ),
    },
    {
        "filename": "司母戊鼎.txt",
        "source": "青铜馆",
        "tags": ["青铜器", "商代"],
        "content": (
            "司母戊鼎出土于河南安阳，是商王祖庚或祖甲为祭祀其母戊所制。"
            "鼎重832.84公斤，高133厘米，口长110厘米，口宽79厘米，"
            "是目前已知中国古代最重的青铜器。鼎身呈长方形，立耳、折沿、"
            "腹部呈长方形，下承四柱足。器腹四转角、上下缘中部、足上部均置扉棱。"
            "鼎身纹饰以兽面纹为主，辅以夔纹、云雷纹，线条粗犷有力。"
            "四足上部饰兽面纹，下部饰三角纹，展现出商代晚期青铜铸造的巅峰技艺。"
            "此鼎采用泥范法铸造，鼎体浑铸，鼎耳后铸，体现了当时高超的铸造工艺。"
            "司母戊鼎不仅是权力的象征，更是商代青铜文明的杰出代表。"
        ),
    },
    {
        "filename": "曾侯乙编钟.txt",
        "source": "青铜馆",
        "tags": ["青铜器", "战国"],
        "content": (
            "曾侯乙编钟出土于湖北随州曾侯乙墓，属战国早期，距今约2400年。"
            "全套编钟共65件，分三层八组悬挂在曲尺形的铜木结构钟架上。"
            "上层为钮钟，共19件；中层为甬钟，共33件；下层为大型甬钟，共12件，"
            "另有一件博钟是楚惠王赠送的。编钟的音域跨越五个半八度，"
            "十二个半音齐备，可演奏五声、六声或七声音阶的乐曲。"
            "每件钟都能发出两个不同的乐音，敲击钟的正面和侧面可分别发出三度音程的两个音。"
            "钟体表面铸有错金铭文，记载着编号、记事、标音及乐律关系。"
            "这套编钟的出土改写了世界音乐史，证明中国早在战国时期就已掌握完整的十二平均律。"
            "它是中国古代礼乐制度的重要见证，也是青铜铸造技术的巅峰之作。"
        ),
    },
    {
        "filename": "长信宫灯.txt",
        "source": "青铜馆",
        "tags": ["青铜器", "汉代"],
        "content": (
            "长信宫灯出土于河北满城汉墓，为西汉中山靖王刘胜之妻窦绾墓中随葬品。"
            "灯具通高48厘米，重15.85公斤，通体鎏金，灿烂生辉。"
            "宫女跪坐执灯，左手执灯座，右臂高举袖口下垂形成灯罩，"
            "整体造型为跪地执灯的年轻宫女，神态恬静优雅。"
            "灯罩由两块弧形屏板组成，可左右开合，随意调节灯光照度和方向。"
            "宫女体内中空，右臂与烟道相通，点燃后烟尘顺右臂进入体内，"
            "溶于底部盛水盘中，保持室内清洁，体现了汉代人的环保智慧。"
            "灯座、灯盘、灯罩等部件均可拆卸，便于清洗。"
            "灯身刻有九处铭文，共65字，记载了灯的容量、重量及所属者，"
            "其中有长信宫字样，故定名为长信宫灯。"
            "此灯集造型艺术、实用功能、环保理念于一身，是汉代青铜器中的瑰宝。"
        ),
    },
    {
        "filename": "金缕玉衣.txt",
        "source": "玉器馆",
        "tags": ["玉器", "汉代"],
        "content": (
            "金缕玉衣主要出土于汉代诸侯王墓，是汉代规格最高的丧葬殓服。"
            "玉衣又称玉匣、玉柙，由脸盖、头罩、上衣前片和后片、左右袖筒、"
            "左右手套、左右裤筒、左右足套及鞋组成，外观与人体形状相同。"
            "以金丝编缀玉片而成，称为金缕玉衣；以银丝编缀者称银缕玉衣；"
            "以铜丝编缀者称铜缕玉衣。西汉时期，皇帝、皇后使用金缕玉衣，"
            "诸侯王、列侯始封、贵人、公主使用银缕玉衣，大贵人、长公主使用铜缕玉衣。"
            "玉衣所用玉片多为和田玉，温润细腻。玉片呈长方形、梯形、三角形等形状，"
            "四角钻孔以便穿缀。制作一件玉衣需耗费大量人力物力，"
            "据估计，制作一件金缕玉衣约需玉片2498片，金丝约1100克。"
            "金缕玉衣体现了汉代人对永生的追求，也是等级制度的物化表现。"
            "目前已出土金缕玉衣十余套，其中以河北满城汉墓中山靖王刘胜的金缕玉衣最为完整精美。"
        ),
    },
    {
        "filename": "翠玉白菜.txt",
        "source": "玉器馆",
        "tags": ["玉器", "清代"],
        "content": (
            "翠玉白菜为清代玉雕，现藏于台北故宫博物院，是该院的镇馆之宝之一。"
            "这件玉器长18.7厘米，宽9.1厘米，厚5.07厘米，"
            "由半白半绿的翡翠雕刻而成。工匠巧妙利用翡翠天然的白色和绿色，"
            "将白色部分雕成菜帮，绿色部分雕成菜叶，浑然天成。"
            "菜叶自然反卷，筋脉分明，栩栩如生。"
            "菜叶上还雕有两只小虫，一只螽斯，一只蝗虫，"
            "都是繁殖力强的昆虫，寓意多子多孙。"
            "螽斯和蝗虫的细节刻画入微，须角分明，腿足纤细，"
            "展现了清代玉雕工艺的极致水平。"
            "这件作品原是光绪皇帝妃子瑾妃的嫁妆，象征清白传家、多子多福。"
            "翠玉白菜巧夺天工，因材施艺，是清代玉雕艺术的巅峰之作，"
            "也是中国玉器史上的不朽杰作，吸引着世界各地的游客慕名而来。"
        ),
    },
    {
        "filename": "马踏飞燕.txt",
        "source": "雕塑馆",
        "tags": ["雕塑", "东汉"],
        "content": (
            "马踏飞燕出土于甘肃武威雷台汉墓，为东汉时期青铜雕塑，"
            "现为中国旅游标志。铜马通高34.5厘米，长45厘米，宽13.1厘米，"
            "重7.15公斤，造型为一匹昂首嘶鸣的奔马。"
            "马的头微微偏向左侧，双耳竖起，张口嘶鸣，"
            "三足腾空，右后蹄踏于一只展翅飞翔的燕子之上。"
            "骏马体躯壮实，肌肉线条流畅，马尾上扬，"
            "展现出风驰电掣般的速度感。"
            "最令人惊叹的是，雕塑仅用一只小小的燕子支撑起整个马身，"
            "却达到了完美的力学平衡，展现了汉代工匠高超的铸造技艺。"
            "铜马下的燕子回头惊顾，更衬托出奔马速度之快，"
            "使整件作品充满了动感和张力。"
            "马踏飞燕不仅是雕塑艺术的杰作，更是汉代国力强盛、"
            "昂扬进取精神的象征。它证明了中国古代在力学、铸造学、"
            "美学等方面都达到了很高的水平。"
        ),
    },
    {
        "filename": "千里江山图.txt",
        "source": "书画馆",
        "tags": ["书画", "北宋"],
        "content": (
            "《千里江山图》是北宋画家王希孟的唯一传世作品，"
            "现藏于北京故宫博物院。画卷纵51.5厘米，横1191.5厘米，"
            "绢本设色，青绿山水，气势恢宏，是中国青绿山水的巅峰之作。"
            "王希孟作此画时年仅十八岁，为宋徽宗赵佶亲自指导的宫廷画院学生。"
            "画卷以概括精练的手法、绚丽的色彩和工细的笔致，"
            "表现了祖国山河的雄伟壮观。画面千山万壑争雄竞秀，江河交错，"
            "烟波浩渺，气势十分雄伟壮丽。山间高崖万丈瀑布直下，"
            "曲径通幽，房舍点缀，绿柳红花，长松修竹，景色秀丽。"
            "山水间野渡渔村、水榭楼台、茅屋草舍、水磨长桥各依地势，"
            "与山川湖泊相辉映。画中人物如蚁，不可胜数，"
            "或行于山径，或坐于楼阁，或独钓江中，或行舟水上，"
            "姿态各异，生动自然。此卷继承了唐代青绿山水的画法，"
            "并有所创新，以石青、石绿为主色，间以赭石、花青，"
            "色彩鲜艳而不俗，历经千年仍绚丽如新。"
            "《千里江山图》是中国十大传世名画之一，"
            "代表了中国古代青绿山水的最高成就。"
        ),
    },
    {
        "filename": "洛神赋图.txt",
        "source": "书画馆",
        "tags": ["书画", "东晋"],
        "content": (
            "《洛神赋图》是东晋画家顾恺之根据三国时期文学家曹植的《洛神赋》"
            "创作的绢本设色画，原作已佚，现存为宋代摹本。"
            "画卷纵27.1厘米，横572.8厘米，现藏于北京故宫博物院。"
            "画卷描绘了曹植在洛水边与洛神相遇、相恋、分离的动人故事。"
            "全卷分为五幕：第一幕是曹植率领随从经过洛水，"
            "望见洛神而驻足凝视；第二幕是洛神现身，凌波微步，"
            "若往若还，含情脉脉；第三幕是两人互赠礼物，表达爱慕之情；"
            "第四幕是众神降临，载歌载舞，为二人祝福；"
            "第五幕是终因人神殊途，洛神含泪离去，曹植乘船追赶，"
            "最终只能在岸上遥望远去的洛神，寄托无尽的思念。"
            "顾恺之运用连续式构图法，将故事情节分段呈现，"
            "以山石、林木、河水作为分隔，同时用衣衫飘带、目光视线等"
            "巧妙连接各段，使画面既独立又连贯。"
            "人物造型优美，神态生动，尤其是洛神的形象，"
            "翩若惊鸿，婉若游龙，充分展现了顾恺之高古游丝描的精湛技艺。"
            "《洛神赋图》是中国现存最早的根据文学作品创作的绘画，"
            "开创了中国绘画史上图文结合的叙事传统，"
            "对后世人物画的发展产生了深远影响。"
        ),
    },
    {
        "filename": "何家村窖藏金银器.txt",
        "source": "金银器馆",
        "tags": ["金银器", "唐代"],
        "content": (
            "何家村窖藏于1970年出土于陕西西安南郊何家村，"
            "共出土金银器、宝玉石、贵重药材等文物1000余件，"
            "是20世纪中国考古最重要的发现之一。"
            "这批窖藏文物制作工艺精湛，代表了唐代金银器的最高水平。"
            "其中最著名的有鸳鸯莲瓣纹金碗、舞马衔杯纹银壶、"
            "镶金兽首玛瑙杯等。鸳鸯莲瓣纹金碗共两件，"
            "口径13.5厘米，高5.5厘米，重约400克，"
            "碗身锤揲出两层莲瓣纹，每层十瓣，上层莲瓣中分别錾刻"
            "鸳鸯、鹦鹉、狐狸、鹿等珍禽异兽，下层莲瓣内錾忍冬花。"
            "碗底饰一朵宝相花，外底圈足内刻一只回首鸳鸯。"
            "舞马衔杯纹银壶高18.5厘米，壶身呈扁圆形，"
            "两面各锤出一匹舞马，马长鬃披颈，前腿伸直，后腿弯曲，"
            "口中衔一只酒杯，再现了唐代舞马祝寿的盛景。"
            "镶金兽首玛瑙杯高6.5厘米，长15.6厘米，"
            "由一块罕见的酱红地缠橙黄夹乳白色缟带的玛瑙雕刻而成，"
            "杯口呈圆形，兽首双角，兽嘴处镶金，作为塞子，"
            "造型与西方来通杯相似，是中外文化交流的见证。"
            "何家村窖藏金银器数量之多、工艺之精、品级之高，"
            "在唐代考古中极为罕见，被誉为唐代金银器的宝库。"
        ),
    },
    {
        "filename": "舞马衔杯纹银壶.txt",
        "source": "金银器馆",
        "tags": ["金银器", "唐代"],
        "content": (
            "舞马衔杯纹银壶是唐代金银器的代表作，出土于陕西西安何家村窖藏。"
            "银壶高18.5厘米，口径2.3厘米，底径8.9厘米，重549克。"
            "壶身呈扁圆形，两侧各锤揲出一匹奋首扬尾、衔杯向空中跳跃的舞马。"
            "舞马前腿直立，后腿弯曲，马颈上系有丝带，随风飘扬。"
            "马的肌肉线条流畅，神态生动，栩栩如生。"
            "壶口位于顶部中央，上有覆莲瓣纹盖，盖钮为宝珠形。"
            "壶身通体鎏金，与银白色形成鲜明对比，富丽堂皇。"
            "据《明皇杂录》记载，唐玄宗时曾训练舞马百匹，"
            "每逢千秋节（皇帝生日），舞马便随音乐起舞，"
            "最后以口衔杯向皇帝祝寿。此壶正是这一盛况的生动写照。"
            "舞马衔杯纹银壶工艺精湛，造型优美，"
            "是唐代金银器中的珍品，现藏于陕西历史博物馆。"
        ),
    },
    {
        "filename": "宋代汝窑天青釉洗.txt",
        "source": "陶瓷馆",
        "tags": ["陶瓷", "宋代"],
        "content": (
            "汝窑天青釉洗是宋代五大名窑之一汝窑的代表作。"
            "汝窑位于河南宝丰县大营镇清凉寺村，因古属汝州而得名。"
            "汝窑瓷器以其独特的天青色釉闻名于世，被誉为青瓷之冠。"
            "这件天青釉洗口径13厘米，足径8.7厘米，高3.5厘米。"
            "造型端庄典雅，敞口，浅腹，平底，圈足。"
            "通体施天青色釉，釉面温润如玉，色泽淡雅含蓄。"
            "釉面开有细密的蟹爪纹，是汝窑瓷器的典型特征。"
            "底部有五枚芝麻状支钉痕，为满釉支烧的痕迹。"
            "汝窑瓷器烧造时间极短，仅约二十年，存世量极少，"
            "据统计全世界仅存六十七件，件件都是稀世珍宝。"
            "汝窑瓷器以其素雅高贵的气质，深受宋徽宗喜爱，"
            "专供宫廷使用，民间不得使用。"
            "汝窑天青釉洗代表了宋代瓷器审美的最高境界，"
            "体现了宋人追求简约、含蓄、内敛的美学理念。"
        ),
    },
    {
        "filename": "素纱襌衣.txt",
        "source": "纺织品馆",
        "tags": ["纺织品", "汉代"],
        "content": (
            "素纱襌衣出土于湖南长沙马王堆一号汉墓，"
            "为西汉初期长沙国丞相轪侯夫人辛追的随葬品。"
            "这件襌衣通长128厘米，袖长190厘米，重仅49克，"
            "还不到一两，是世界上最轻薄的丝织衣物。"
            "襌衣用素纱制成，素纱是指没有染色的纱，"
            "经纬密度为每厘米58根和40根，丝缕极细，"
            "丝线直径仅为0.05-0.08毫米，相当于头发丝的五分之一。"
            "整件衣物没有衬里，轻薄透明，折叠后可以放入一个火柴盒中。"
            "制作这样一件襌衣需要技艺精湛的织女花费数年时间，"
            "所用的蚕丝来自三眠蚕，这种蚕吐的丝特别细，"
            "现在已经很难培育出来。"
            "素纱襌衣的领口和袖口用绒圈锦镶边，"
            "增加了衣物的牢固性和美观性。"
            "这种轻薄的衣物在汉代是贵族妇女罩在锦衣外面的服饰，"
            "可以增加一种朦胧的美感，是汉代贵族时尚的体现。"
            "素纱襌衣的出土，证明了中国古代丝织工艺的极高水平，"
            "是丝绸之路闻名世界的重要物证，"
            "也是研究汉代纺织技术的珍贵实物资料。"
        ),
    },
]

SAMPLE_CHAT_SESSIONS = [
    {
        "title": "青铜器咨询",
        "messages": [
            {"role": "user", "content": "请介绍一下四羊方尊的历史背景"},
            {
                "role": "assistant",
                "content": "四羊方尊是商代晚期的青铜礼器，出土于湖南宁乡。它是古代祭祀用的重要器物，将方形器体与立体羊首巧妙结合，展现了商代高超的青铜铸造工艺。",
            },
            {"role": "user", "content": "司母戊鼎和四羊方尊有什么区别？"},
            {
                "role": "assistant",
                "content": "司母戊鼎是商代最重的青铜器，重832公斤，主要用于祭祀；而四羊方尊相对较小，以其独特的四羊造型闻名。两者都代表商代青铜工艺的巅峰。",
            },
            {"role": "user", "content": "曾侯乙编钟有什么特别之处？"},
            {
                "role": "assistant",
                "content": "曾侯乙编钟是战国早期的乐器，共65件，音域跨越五个半八度，十二个半音齐备。它证明中国在2400年前就已掌握完整的十二平均律，改写了世界音乐史。",
            },
        ],
    },
    {
        "title": "书画鉴赏",
        "messages": [
            {"role": "user", "content": "清明上河图描绘的是什么内容？"},
            {
                "role": "assistant",
                "content": "清明上河图是北宋画家张择端的风俗长卷，描绘了汴京及汴河沿岸的繁华景象。画卷细致展现了市井百态、商贸往来和舟车交通，是研究宋代社会的重要图像文献。",
            },
            {"role": "user", "content": "千里江山图为什么出名？"},
            {
                "role": "assistant",
                "content": "千里江山图是北宋画家王希孟的唯一传世作品，长近12米，以青绿山水著称。画家年仅18岁完成此作，代表了中国青绿山水的最高成就，是中国十大传世名画之一。",
            },
            {"role": "user", "content": "洛神赋图讲的是什么故事？"},
            {
                "role": "assistant",
                "content": "洛神赋图是东晋画家顾恺之根据曹植的《洛神赋》创作，描绘曹植与洛神相遇、相恋、分离的故事。它是中国现存最早的文学题材绘画，开创了图文结合的叙事传统。",
            },
        ],
    },
    {
        "title": "综合问答",
        "messages": [
            {"role": "user", "content": "马踏飞燕为什么成为中国旅游标志？"},
            {
                "role": "assistant",
                "content": "马踏飞燕是东汉青铜雕塑，造型为一匹奔马踏在飞燕之上，展现了完美的力学平衡和汉代工匠的高超技艺。它象征着昂扬进取的精神，1983年被定为中国旅游标志。",
            },
            {"role": "user", "content": "金缕玉衣是什么人使用的？"},
            {
                "role": "assistant",
                "content": "金缕玉衣是汉代规格最高的丧葬殓服，只有皇帝和皇后才能使用。诸侯王使用银缕玉衣，其他人使用铜缕玉衣。它体现了汉代的等级制度和对永生的追求。",
            },
            {"role": "user", "content": "翠玉白菜有什么寓意？"},
            {
                "role": "assistant",
                "content": "翠玉白菜是清代玉雕杰作，巧妙利用翡翠天然的青白两色雕刻而成。菜叶上的螽斯和蝗虫寓意多子多孙，整体象征清白传家、多子多福。",
            },
            {"role": "user", "content": "素纱襌衣为什么这么轻薄？"},
            {
                "role": "assistant",
                "content": "素纱襌衣重仅49克，是世界上最轻薄的丝织衣物。它使用三眠蚕的丝，丝线直径仅0.05-0.08毫米。整件衣物可放入火柴盒，展现了汉代纺织工艺的极高水平。",
            },
        ],
    },
]


async def init_documents(
    session_maker,
    es_client: ElasticsearchClient,
    embeddings: CustomOllamaEmbeddings,
    user_id: str,
) -> None:
    """Initialize sample documents."""
    ingestion_service = IngestionService(
        es_client=es_client,
        embeddings=embeddings,
    )

    created_count = 0
    skipped_count = 0

    for item in SAMPLE_DOCUMENTS:
        async with get_session(session_maker) as session:
            result = await session.execute(select(Document).where(Document.filename == item["filename"]))
            existing_doc = result.scalars().first()

            if existing_doc:
                print(f"  Document already exists: {item['filename']}")
                skipped_count += 1
                continue

            doc_id = str(uuid.uuid4())
            document = Document(id=doc_id, user_id=user_id, filename=item["filename"], status="pending")
            session.add(document)

            job_id = str(uuid.uuid4())
            job = IngestionJob(id=job_id, document_id=doc_id, status="pending")
            session.add(job)
            await session.flush()

            try:
                job = await ingestion_service.process_document(session, doc_id, item["content"], item["source"])
                # Update document status based on ingestion job result
                if job.status == "completed":
                    document.status = "completed"
                    await session.flush()
                created_count += 1
                print(f"  Created document: {item['filename']}")
            except Exception as e:
                await session.rollback()
                print(f"  Failed to create document {item['filename']}: {e}")
                continue

    print(f"\nDocuments: {created_count} created, {skipped_count} skipped")


async def init_chat_data(session_maker, user_id: str) -> None:
    """Initialize sample chat sessions and messages."""
    created_sessions = 0
    skipped_sessions = 0
    created_messages = 0

    for session_data in SAMPLE_CHAT_SESSIONS:
        async with get_session(session_maker) as session:
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.user_id == user_id,
                    ChatSession.title == session_data["title"],
                )
            )
            existing_session = result.scalars().first()

            if existing_session:
                print(f"  Chat session already exists: {session_data['title']}")
                skipped_sessions += 1
                continue

            session_id = str(uuid.uuid4())
            chat_session = ChatSession(
                id=session_id,
                user_id=user_id,
                title=session_data["title"],
            )
            session.add(chat_session)

            for msg_data in session_data["messages"]:
                message_id = str(uuid.uuid4())
                message = ChatMessage(
                    id=message_id,
                    session_id=session_id,
                    role=msg_data["role"],
                    content=msg_data["content"],
                )
                session.add(message)
                created_messages += 1

            await session.commit()
            created_sessions += 1
            print(f"  Created chat session: {session_data['title']} ({len(session_data['messages'])} messages)")

    print(f"\nChat sessions: {created_sessions} created, {skipped_sessions} skipped")
    print(f"Chat messages: {created_messages} created")


async def main() -> None:
    """Main entry point."""
    settings = get_settings()
    print(f"Initializing test data for {settings.APP_NAME}...")
    print("=" * 50)

    # Check database URL is not the default in-memory SQLite
    if settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:":
        print("ERROR: Using default in-memory SQLite database.")
        print("Please set DATABASE_URL in .env file or environment variable.")
        print("Example: DATABASE_URL=postgresql+asyncpg://museai:museai123@localhost:5432/museai")
        sys.exit(1)

    print(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print(f"Elasticsearch: {settings.ELASTICSEARCH_URL}")
    print(f"Embedding: {settings.EMBEDDING_OLLAMA_BASE_URL} ({settings.EMBEDDING_OLLAMA_MODEL})")
    print()

    # Use init_database to ensure tables are created
    session_maker = await init_database(settings.DATABASE_URL)

    es_client = ElasticsearchClient(
        hosts=[settings.ELASTICSEARCH_URL],
        index_name=settings.ELASTICSEARCH_INDEX,
    )

    embeddings = CustomOllamaEmbeddings(
        base_url=settings.EMBEDDING_OLLAMA_BASE_URL,
        model=settings.EMBEDDING_OLLAMA_MODEL,
        dims=settings.EMBEDDING_DIMS,
    )

    await es_client.create_index(settings.ELASTICSEARCH_INDEX, dims=settings.EMBEDDING_DIMS)
    print(f"ES index '{settings.ELASTICSEARCH_INDEX}' ready\n")

    async with get_session(session_maker) as session:
        result = await session.execute(select(User).where(User.id == "user-001"))
        user = result.scalars().first()
        if not user:
            user = User(id="user-001", email="test@museai.local", password_hash="test")
            session.add(user)
            await session.commit()
            print("Created test user: user-001\n")
        else:
            print("Test user already exists: user-001\n")
        user_id = user.id

    try:
        print("Initializing documents...")
        print("-" * 50)
        await init_documents(session_maker, es_client, embeddings, user_id)

        print("\nInitializing chat data...")
        print("-" * 50)
        await init_chat_data(session_maker, user_id)
    finally:
        await es_client.close()

    print("\n" + "=" * 50)
    print("Test data initialization complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
