import uiScriptLocale

## The guild war top killers (NOVA-29; OLD uiscript/GuildTopWarPlayers.py): both guilds'
## fighters, each side's name with its score and its MVP, and per fighter the kills,
## deaths, damage and ping of this war. Held open with TAB during a war. OLD's art
## (guild_board/*) and its scroll lists are not in NEW's packs: a board with a title
## bar, the rows uiguild.py's TopWarPlayersDialog makes in code (TOP_WAR_ROWS a side).

window = {
	"name" : "TopWarPlayersDialog",
	"style" : ("float",),

	"x" : (SCREEN_WIDTH - 720) / 2,
	"y" : (SCREEN_HEIGHT - 340) / 2,

	"width" : 720,
	"height" : 340,

	"children" :
	(
		{
			"name" : "Board",
			"type" : "board",
			"style" : ("attach",),

			"x" : 0,
			"y" : 0,

			"width" : 720,
			"height" : 340,

			"children" :
			(
				{
					"name" : "TitleBar",
					"type" : "titlebar",
					"style" : ("attach",),

					"x" : 8,
					"y" : 7,

					"width" : 705,
					"color" : "red",

					"children" :
					(
						{ "name" : "TitleName", "type" : "text", "x" : 0, "y" : 3, "text" : uiScriptLocale.GUILD_WAR_TOP_TITLE, "horizontal_align" : "center", "text_horizontal_align" : "center" },
					),
				},
				{ "name" : "guild1_name", "type" : "text", "x" : 20, "y" : 36, "text" : "" },
				{ "name" : "guild1_mvp", "type" : "text", "x" : 20, "y" : 54, "text" : "" },
				{ "name" : "guild1_head_name", "type" : "text", "x" : 20, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_NAME },
				{ "name" : "guild1_head_kills", "type" : "text", "x" : 150, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_KILLS },
				{ "name" : "guild1_head_deaths", "type" : "text", "x" : 195, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_DEATHS },
				{ "name" : "guild1_head_damage", "type" : "text", "x" : 245, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_DAMAGE },
				{ "name" : "guild1_head_ping", "type" : "text", "x" : 310, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_PING },
				{ "name" : "guild2_name", "type" : "text", "x" : 370, "y" : 36, "text" : "" },
				{ "name" : "guild2_mvp", "type" : "text", "x" : 370, "y" : 54, "text" : "" },
				{ "name" : "guild2_head_name", "type" : "text", "x" : 370, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_NAME },
				{ "name" : "guild2_head_kills", "type" : "text", "x" : 500, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_KILLS },
				{ "name" : "guild2_head_deaths", "type" : "text", "x" : 545, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_DEATHS },
				{ "name" : "guild2_head_damage", "type" : "text", "x" : 595, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_DAMAGE },
				{ "name" : "guild2_head_ping", "type" : "text", "x" : 660, "y" : 78, "text" : uiScriptLocale.GUILD_WAR_TOP_PING },
			),
		},
	),
}
