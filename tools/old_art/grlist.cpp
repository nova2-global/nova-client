// grlist: the textures Granny models name, and the conversion of OLD's custom
// models (tag 0x71000039, OLD Tools/preproc ConvertToCustom) to standard ones.
//   grlist list <list>     one model per line; prints model\tkind\tname
//   grlist convert <list>  "source\tdestination" per line; writes a standard
//                          file for a custom one (OLD EterGrnLib/Thing.cpp
//                          GetMyFileInfo: the vertices back by one byte)
//   grlist compare <list>  "source\tdestination": the meshes' vertices and
//                          indices of both, as each loader reads them, match
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "granny.h"

namespace
{
struct my_file_info
{
	granny_file_info* FileInfo;
};

const granny_uint32 kCustomTag = (granny_uint32)GrannyCurrentGRNStandardTag - (granny_uint32)GrannyFirstGRNStandardTag + 0x71000000;

granny_file_info* Info(granny_file* file, bool* custom)
{
	*custom = file->Header && file->Header->TypeTag == kCustomTag;
	if (!*custom)
		return GrannyGetFileInfo(file);
	granny_variant root;
	GrannyGetDataTreeFromFile(file, &root);
	my_file_info* mine = static_cast<my_file_info*>(root.Object);
	if (!mine || !mine->FileInfo)
		return nullptr;
	for (int i = 0; i < mine->FileInfo->MeshCount; ++i)
	{
		granny_mesh* mesh = mine->FileInfo->Meshes[i];
		if (mesh && mesh->PrimaryVertexData)
			mesh->PrimaryVertexData->Vertices = mesh->PrimaryVertexData->Vertices - granny_uint8(1);
	}
	return mine->FileInfo;
}

void PrintMaterial(const char* name, granny_material* m)
{
	if (!m) return;
	granny_texture* d = GrannyGetMaterialTextureByType(m, GrannyDiffuseColorTexture);
	granny_texture* o = GrannyGetMaterialTextureByType(m, GrannyOpacityTexture);
	if (d && d->FromFileName) std::printf("%s\tdiffuse\t%s\n", name, d->FromFileName);
	if (o && o->FromFileName) std::printf("%s\topacity\t%s\n", name, o->FromFileName);
}

void PrintTextures(const char* name, granny_file_info* info)
{
	for (int i = 0; i < info->MaterialCount; ++i)
		PrintMaterial(name, info->Materials[i]);
	for (int i = 0; i < info->MeshCount; ++i)
		if (info->Meshes[i])
			for (int j = 0; j < info->Meshes[i]->MaterialBindingCount; ++j)
				PrintMaterial(name, info->Meshes[i]->MaterialBindings[j].Material);
	for (int i = 0; i < info->TextureCount; ++i)
		if (info->Textures[i] && info->Textures[i]->FromFileName)
			std::printf("%s\ttexture\t%s\n", name, info->Textures[i]->FromFileName);
}

bool Write(granny_file* file, granny_file_info* info, const char* out)
{
	granny_file_builder* builder = GrannyBeginFile(GrannyStandardSectionCount, GrannyCurrentGRNStandardTag,
		GrannyGRNFileMV_ThisPlatform, GrannyGetTemporaryDirectory(), "Prefix");
	granny_grn_section* sections = GrannyGetGRNSectionArray(file->Header);
	for (int i = 0; i < file->SectionCount && i < GrannyStandardSectionCount; ++i)
		GrannySetFileSectionFormat(builder, i, GrannyBitKnit2Compression, sections[i].InternalAlignment);
	granny_file_data_tree_writer* writer = GrannyBeginFileDataTreeWriting(GrannyFileInfoType, info, GrannyStandardDiscardableSection, 0);
	GrannyWriteDataTreeToFileBuilder(writer, builder);
	GrannyEndFileDataTreeWriting(writer);
	return GrannyEndFile(builder, out) != 0;
}
}

bool SameMeshes(granny_file_info* a, granny_file_info* b)
{
	if (a->MeshCount != b->MeshCount) return false;
	for (int i = 0; i < a->MeshCount; ++i)
	{
		granny_mesh* x = a->Meshes[i];
		granny_mesh* y = b->Meshes[i];
		if (!x || !y || !x->PrimaryVertexData || !y->PrimaryVertexData) return x == y;
		const int nx = x->PrimaryVertexData->VertexCount, ny = y->PrimaryVertexData->VertexCount;
		if (nx != ny) return false;
		const int sx = GrannyGetTotalObjectSize(x->PrimaryVertexData->VertexType);
		if (sx != GrannyGetTotalObjectSize(y->PrimaryVertexData->VertexType)) return false;
		if (std::memcmp(x->PrimaryVertexData->Vertices, y->PrimaryVertexData->Vertices, (size_t)nx * sx) != 0) return false;
		if (GrannyGetMeshIndexCount(x) != GrannyGetMeshIndexCount(y)) return false;
		if (GrannyGetMeshBytesPerIndex(x) != GrannyGetMeshBytesPerIndex(y)) return false;
		if (std::memcmp(GrannyGetMeshIndices(x), GrannyGetMeshIndices(y),
				(size_t)GrannyGetMeshIndexCount(x) * GrannyGetMeshBytesPerIndex(x)) != 0) return false;
	}
	return a->ModelCount == b->ModelCount && a->AnimationCount == b->AnimationCount &&
		a->MaterialCount == b->MaterialCount && a->TextureCount == b->TextureCount;
}

int main(int argc, char** argv)
{
	if (argc < 3) { std::fprintf(stderr, "usage: grlist list|convert <list>\n"); return 2; }
	const bool convert = std::strcmp(argv[1], "convert") == 0;
	const bool compare = std::strcmp(argv[1], "compare") == 0;
	FILE* list = std::fopen(argv[2], "r");
	if (!list) { std::fprintf(stderr, "cannot open %s\n", argv[2]); return 2; }
	char line[2048];
	int failed = 0;
	while (std::fgets(line, sizeof(line), list))
	{
		line[std::strcspn(line, "\r\n")] = 0;
		if (!*line) continue;
		char* out = nullptr;
		if (compare)
		{
			out = std::strchr(line, '\t');
			if (!out) { std::printf("%s\tERROR\tno destination\n", line); ++failed; continue; }
			*out++ = 0;
			granny_file* fa = GrannyReadEntireFile(line);
			granny_file* fb = GrannyReadEntireFile(out);
			bool ca = false, cb = false;
			granny_file_info* ia = fa ? Info(fa, &ca) : nullptr;
			granny_file_info* ib = fb ? Info(fb, &cb) : nullptr;
			const bool same = ia && ib && !cb && SameMeshes(ia, ib);
			std::printf("%s\t%s\t%s\n", line, same ? "SAME" : "DIFFERENT", out);
			if (!same) ++failed;
			if (fa) GrannyFreeFile(fa);
			if (fb) GrannyFreeFile(fb);
			continue;
		}
		if (convert)
		{
			out = std::strchr(line, '\t');
			if (!out) { std::printf("%s\tERROR\tno destination\n", line); ++failed; continue; }
			*out++ = 0;
		}
		granny_file* file = GrannyReadEntireFile(line);
		if (!file) { std::printf("%s\tERROR\tread\n", line); ++failed; continue; }
		bool custom = false;
		granny_file_info* info = Info(file, &custom);
		if (!info) { std::printf("%s\tERROR\tinfo\n", line); ++failed; GrannyFreeFile(file); continue; }
		PrintTextures(line, info);
		if (convert && custom && !Write(file, info, out)) { std::printf("%s\tERROR\twrite\n", line); ++failed; }
		std::printf("%s\t%s\t%d %d %d %d\n", line, custom ? "CUSTOM" : "STANDARD",
			info->MeshCount, info->ModelCount, info->AnimationCount, info->MaterialCount);
		GrannyFreeFile(file);
	}
	std::fclose(list);
	return failed ? 1 : 0;
}
